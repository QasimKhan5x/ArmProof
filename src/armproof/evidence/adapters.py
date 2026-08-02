"""Public evidence-adapter boundary and built-in raw evidence adapters."""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import asdict
from importlib.metadata import entry_points
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Protocol

from armproof.contracts import Contract, validate_comparison_identities
from armproof.domain import Comparison, TreatmentIdentity
from armproof.evidence.checksums import verify_checksum_ledger
from armproof.evidence.pipeline import (
    ADAPTER_ID,
    VerifiedEvidence,
    _passes,
    _samples,
    verify_and_derive,
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
        fields = {"adapter", "root", "checksums", "workload_manifest", "reproduction"}
        _exact_config(config, fields, self.adapter_id)
        reproduction = config.get("reproduction")
        if not isinstance(reproduction, Mapping) or set(reproduction) != {"root", "checksums"}:
            raise ValueError("reference adapter reproduction requires root and checksums")
        return verify_and_derive(
            contract,
            _path(base, config["root"], "root"),
            _path(base, config["checksums"], "checksums"),
            _path(base, config["workload_manifest"], "workload_manifest"),
            _path(base, reproduction["root"], "reproduction.root"),
            _path(base, reproduction["checksums"], "reproduction.checksums"),
        )


def _identity(contract: Contract, treatment_id: str) -> TreatmentIdentity:
    treatment = next(
        (item for item in contract.treatments if item.treatment_id == treatment_id), None
    )
    if treatment is None:
        raise ValueError(f"adapter treatment is absent from contract: {treatment_id}")
    return TreatmentIdentity(
        treatment_id=treatment.treatment_id,
        artifact_sha256=treatment.artifact_sha256,
        runtime_sha256=treatment.runtime_sha256,
        workload_sha256=treatment.workload_sha256,
        environment_sha256=treatment.environment_sha256,
        controls=MappingProxyType(dict(treatment.environment)),
    )


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"adapter JSON must contain an object: {path}")
    return payload


class HttpSloAdapter:
    """Derive a fixed-SLO capacity bracket for any bounded HTTP inference service."""

    adapter_id = "http-slo-v1"

    def verify(
        self, contract: Contract, config: Mapping[str, Any], base: Path
    ) -> VerifiedEvidence:
        fields = {"adapter", "root", "checksums", "protocol"}
        _exact_config(config, fields, self.adapter_id)
        root = _path(base, config["root"], "root")
        checksums = verify_checksum_ledger(
            _path(base, config["checksums"], "checksums"), root
        )
        if not checksums.passed:
            raise ValueError(
                f"checksum verification failed: missing={checksums.missing}, "
                f"mismatched={checksums.mismatched}"
            )
        protocol_path = _path(base, config["protocol"], "protocol").resolve()
        if not protocol_path.is_relative_to(root.resolve()):
            raise ValueError("HTTP SLO protocol must be inside the checksummed evidence root")
        protocol = _json(protocol_path)
        expected = {
            "schema_version", "comparison_id", "measurement_seconds", "p95_slo_ms",
            "max_error_rate", "minimum_delivery_ratio", "minimum_requests_per_file",
            "baseline_treatment_id", "treatment_treatment_id", "boundaries",
            "arm_attribution",
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
                    samples = _samples(root / relative)
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
        baseline_arm = bool(pattern.search(
            (root / str(attribution["baseline_profile"])).read_text(
                encoding="utf-8", errors="replace"
            )
        ))
        treatment_arm = bool(pattern.search(
            (root / str(attribution["treatment_profile"])).read_text(
                encoding="utf-8", errors="replace"
            )
        ))
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
            baseline=_identity(contract, str(protocol["baseline_treatment_id"])),
            treatment=_identity(contract, str(protocol["treatment_treatment_id"])),
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
