"""Public evidence-adapter boundary and built-in raw evidence adapters."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from importlib.metadata import entry_points
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Protocol

from armproof.contracts import Contract, validate_comparison_identities
from armproof.domain import Comparison, TreatmentIdentity
from armproof.evidence.checksums import checksum_ledger_paths, verify_checksum_ledger
from armproof.evidence.pipeline import (
    ADAPTER_ID,
    VerifiedEvidence,
    _passes,
    _samples,
    verify_and_derive,
)
from armproof.evidence.performix import (
    PERFORMIX_CONFIG_FIELDS,
    verify_performix_archive,
)
from armproof.policy.statistics import estimate_capacity_bracket
from armproof.workload import SloPolicy, summarize_samples


ENTRY_POINT_GROUP = "armproof.evidence_adapters"


class EvidenceAdapter(Protocol):
    """Convert checksum-bound raw evidence into one contract comparison."""

    adapter_id: str

    def verify(
        self,
        contract: Contract,
        config: Mapping[str, Any],
        base: Path,
    ) -> VerifiedEvidence: ...


def _path(base: Path, value: Any, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"adapter field {field} must be a non-empty path")
    return base / value


def _exact_config(config: Mapping[str, Any], fields: set[str], adapter_id: str) -> None:
    if set(config) != fields:
        raise ValueError(
            f"{adapter_id} evidence config requires exactly {sorted(fields)}"
        )


class KleidiAICapacityAdapter:
    adapter_id = ADAPTER_ID

    def verify(
        self, contract: Contract, config: Mapping[str, Any], base: Path
    ) -> VerifiedEvidence:
        fields = {
            "adapter", "root", "checksums", "workload_manifest", "reproduction",
            "performix",
        }
        _exact_config(config, fields, self.adapter_id)
        reproduction = config.get("reproduction")
        if not isinstance(reproduction, Mapping) or set(reproduction) != {"root", "checksums"}:
            raise ValueError("reference adapter reproduction requires root and checksums")
        performix = config.get("performix")
        if not isinstance(performix, Mapping) or set(performix) != PERFORMIX_CONFIG_FIELDS:
            raise ValueError(
                "reference adapter performix requires exactly "
                f"{sorted(PERFORMIX_CONFIG_FIELDS)}"
            )
        verified = verify_and_derive(
            contract,
            _path(base, config["root"], "root"),
            _path(base, config["checksums"], "checksums"),
            _path(base, config["workload_manifest"], "workload_manifest"),
            _path(base, reproduction["root"], "reproduction.root"),
            _path(base, reproduction["checksums"], "reproduction.checksums"),
        )
        profile = verify_performix_archive(
            _path(base, performix["archive"], "performix.archive"),
            expected_archive_sha256=str(performix["archive_sha256"]),
            expected_experiment_id=str(performix["experiment_id"]),
            disabled_run_id=str(performix["disabled_run_id"]),
            enabled_run_id=str(performix["enabled_run_id"]),
            linux_perf_share=float(performix["linux_perf_kai_cycle_share"]),
            maximum_share_difference=float(performix["maximum_share_difference"]),
        )
        summary = {**dict(verified.summary), "performix": profile}
        return VerifiedEvidence(
            comparison=verified.comparison,
            summary=MappingProxyType(summary),
            checksums=verified.checksums,
            reproduction_checksums=verified.reproduction_checksums,
            performix=MappingProxyType(profile),
            adapter=verified.adapter,
        )


def _identity(payload: Mapping[str, Any], treatment_id: str) -> TreatmentIdentity:
    required = {
        "treatment_id", "artifact_sha256", "runtime_sha256", "workload_sha256",
        "environment_sha256", "controls",
    }
    if (
        not isinstance(payload, Mapping)
        or set(payload) != required
        or payload.get("treatment_id") != treatment_id
    ):
        raise ValueError(f"observed identity is invalid: {treatment_id}")
    digests = {
        name: payload[name]
        for name in (
            "artifact_sha256", "runtime_sha256", "workload_sha256",
            "environment_sha256",
        )
    }
    if any(
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
        for value in digests.values()
    ) or not isinstance(payload["controls"], Mapping):
        raise ValueError(f"observed identity fields are invalid: {treatment_id}")
    return TreatmentIdentity(
        treatment_id=treatment_id,
        artifact_sha256=digests["artifact_sha256"],
        runtime_sha256=digests["runtime_sha256"],
        workload_sha256=digests["workload_sha256"],
        environment_sha256=digests["environment_sha256"],
        controls=MappingProxyType(dict(payload["controls"])),
    )


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"adapter JSON must contain an object: {path}")
    return payload


def _bound_file(root: Path, candidate: Path, ledger_paths: set[str], field: str) -> Path:
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    if not resolved.is_relative_to(resolved_root):
        raise ValueError(f"HTTP SLO {field} must be inside the evidence root")
    relative = resolved.relative_to(resolved_root).as_posix()
    if relative not in ledger_paths:
        raise ValueError(f"HTTP SLO {field} is absent from the checksum ledger: {relative}")
    if not resolved.is_file():
        raise ValueError(f"HTTP SLO {field} is not a file: {relative}")
    return resolved


class HttpSloAdapter:
    """Derive a fixed-SLO capacity bracket for any bounded HTTP inference service."""

    adapter_id = "http-slo-v1"

    def verify(
        self, contract: Contract, config: Mapping[str, Any], base: Path
    ) -> VerifiedEvidence:
        fields = {"adapter", "root", "checksums", "protocol"}
        _exact_config(config, fields, self.adapter_id)
        root = _path(base, config["root"], "root")
        ledger = _path(base, config["checksums"], "checksums")
        checksums = verify_checksum_ledger(ledger, root)
        if not checksums.passed:
            raise ValueError(
                f"checksum verification failed: missing={checksums.missing}, "
                f"mismatched={checksums.mismatched}"
            )
        ledger_paths = set(checksum_ledger_paths(ledger))
        protocol_path = _bound_file(
            root,
            _path(base, config["protocol"], "protocol"),
            ledger_paths,
            "protocol",
        )
        protocol = _json(protocol_path)
        expected = {
            "schema_version", "comparison_id", "measurement_seconds", "p95_slo_ms",
            "max_error_rate", "minimum_delivery_ratio", "minimum_requests_per_file",
            "baseline_treatment_id", "treatment_treatment_id", "boundaries",
            "arm_attribution", "identity_manifest",
        }
        if set(protocol) != expected or protocol["schema_version"] != "1.0.0":
            raise ValueError("HTTP SLO protocol has unsupported fields or schema")
        seconds = float(protocol["measurement_seconds"])
        minimum_rows = int(protocol["minimum_requests_per_file"])
        if seconds <= 0 or minimum_rows < 1:
            raise ValueError("HTTP SLO measurement requirements are invalid")
        policy = SloPolicy(
            float(protocol["p95_slo_ms"]),
            float(protocol["max_error_rate"]),
            float(protocol["minimum_delivery_ratio"]),
        )
        boundary_config = protocol["boundaries"]
        if not isinstance(boundary_config, Mapping) or set(boundary_config) != {
            "baseline", "treatment"
        }:
            raise ValueError("HTTP SLO boundaries require baseline and treatment")
        rates: dict[str, dict[str, list[float]]] = {
            name: {outcome: [] for outcome in ("pass", "fail")}
            for name in ("baseline", "treatment")
        }
        minimum_observed = None
        for name in ("baseline", "treatment"):
            outcomes = boundary_config[name]
            if not isinstance(outcomes, Mapping) or set(outcomes) != {"pass", "fail"}:
                raise ValueError(f"HTTP SLO {name} requires pass and fail files")
            for outcome in ("pass", "fail"):
                paths = outcomes[outcome]
                if not isinstance(paths, list) or len(paths) < 3:
                    raise ValueError("each HTTP SLO boundary requires at least three files")
                for relative in paths:
                    samples = _samples(_bound_file(
                        root,
                        root / str(relative),
                        ledger_paths,
                        f"{name}.{outcome} boundary",
                    ))
                    if len(samples) < minimum_rows:
                        raise ValueError(
                            f"HTTP SLO boundary has fewer than {minimum_rows} requests: {relative}"
                        )
                    minimum_observed = (
                        len(samples) if minimum_observed is None
                        else min(minimum_observed, len(samples))
                    )
                    summary = summarize_samples(samples, seconds)
                    offered = len(samples) / seconds
                    passed = _passes(summary, offered, policy)
                    if passed != (outcome == "pass"):
                        raise ValueError(f"HTTP SLO {outcome} evidence disagrees: {relative}")
                    rates[name][outcome].append(
                        summary.accepted_rps if outcome == "pass" else offered
                    )
        bracket = estimate_capacity_bracket(
            rates["baseline"]["pass"],
            rates["baseline"]["fail"],
            rates["treatment"]["pass"],
            rates["treatment"]["fail"],
        )
        attribution = protocol["arm_attribution"]
        if not isinstance(attribution, Mapping) or set(attribution) != {
            "baseline_profile", "treatment_profile", "symbol_regex"
        }:
            raise ValueError("HTTP SLO Arm attribution config is invalid")
        pattern = re.compile(str(attribution["symbol_regex"]))
        baseline_profile = _bound_file(
            root,
            root / str(attribution["baseline_profile"]),
            ledger_paths,
            "baseline profile",
        )
        treatment_profile = _bound_file(
            root,
            root / str(attribution["treatment_profile"]),
            ledger_paths,
            "treatment profile",
        )
        baseline_arm = bool(pattern.search(
            baseline_profile.read_text(
                encoding="utf-8", errors="replace"
            )
        ))
        treatment_arm = bool(pattern.search(
            treatment_profile.read_text(
                encoding="utf-8", errors="replace"
            )
        ))
        identities = _json(_bound_file(
            root,
            root / str(protocol["identity_manifest"]),
            ledger_paths,
            "identity manifest",
        ))
        if set(identities) != {"schema_version", "baseline", "treatment"} or (
            identities.get("schema_version") != "1.0.0"
        ):
            raise ValueError("HTTP SLO identity manifest is invalid")
        comparison_ids = {claim.comparison_id for claim in contract.claims}
        scopes = {claim.causal_scope for claim in contract.claims}
        if comparison_ids != {protocol["comparison_id"]} or len(scopes) != 1:
            raise ValueError("HTTP SLO contract must declare one comparison and causal scope")
        metrics = {
            "tested_capacity_ratio": bracket.tested_ratio,
            "capacity_ratio_lower_bound": bracket.lower_bound,
            "capacity_ratio_upper_bound": bracket.upper_bound,
            "baseline_pass_rps": bracket.baseline_pass,
            "baseline_fail_rps": bracket.baseline_fail,
            "treatment_pass_rps": bracket.treatment_pass,
            "treatment_fail_rps": bracket.treatment_fail,
            "minimum_requests_per_boundary": float(minimum_observed or 0),
            "arm_path_treatment_observed": float(treatment_arm),
        }
        comparison = Comparison(
            comparison_id=str(protocol["comparison_id"]),
            causal_scope=next(iter(scopes)),
            baseline=_identity(
                identities["baseline"], str(protocol["baseline_treatment_id"])
            ),
            treatment=_identity(
                identities["treatment"], str(protocol["treatment_treatment_id"])
            ),
            metrics=MappingProxyType(metrics),
            evidence_kinds=frozenset({
                "request_samples", "boundary_confirmations", "artifact_hashes",
                "arm_callchains",
            }),
            arm_path_baseline_observed=baseline_arm,
            arm_path_treatment_observed=treatment_arm,
        )
        validate_comparison_identities(contract, (comparison,))
        summary = {
            "schema_version": "1.0.0",
            "adapter": self.adapter_id,
            "passed": True,
            "mixes": {"default": {
                "valid_boundary_confirmations": True,
                "disabled_boundary": [bracket.baseline_pass, bracket.baseline_fail],
                "enabled_boundary": [bracket.treatment_pass, bracket.treatment_fail],
                "capacity_bracket": asdict(bracket),
                "ratio": {
                    "baseline_median": bracket.baseline_pass,
                    "treatment_median": bracket.treatment_pass,
                    "ratio": bracket.tested_ratio,
                },
            }},
            "minimum_requests_per_boundary": minimum_observed,
        }
        return VerifiedEvidence(
            comparison=comparison,
            summary=MappingProxyType(summary),
            checksums=checksums,
            reproduction_checksums=None,
            adapter=self.adapter_id,
        )


BUILTIN_ADAPTERS: dict[str, EvidenceAdapter] = {
    ADAPTER_ID: KleidiAICapacityAdapter(),
    HttpSloAdapter.adapter_id: HttpSloAdapter(),
}


def list_evidence_adapters() -> tuple[str, ...]:
    """List built-in and installed plugin adapter identifiers."""
    names = set(BUILTIN_ADAPTERS)
    names.update(entry.name for entry in entry_points().select(group=ENTRY_POINT_GROUP))
    return tuple(sorted(names))


def get_evidence_adapter(adapter_id: str) -> EvidenceAdapter:
    if adapter_id in BUILTIN_ADAPTERS:
        return BUILTIN_ADAPTERS[adapter_id]
    discovered = entry_points().select(group=ENTRY_POINT_GROUP)
    for entry in discovered:
        if entry.name == adapter_id:
            loaded = entry.load()
            return loaded() if isinstance(loaded, type) else loaded
    available = sorted({*BUILTIN_ADAPTERS, *(entry.name for entry in discovered)})
    raise ValueError(
        f"unsupported evidence adapter: {adapter_id}; available: {', '.join(available)}"
    )
