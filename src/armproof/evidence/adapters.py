"""Public evidence-adapter boundary and built-in raw evidence adapters."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, replace
from importlib.metadata import entry_points
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Protocol

from armproof.contracts import Contract, validate_comparison_identities
from armproof.domain import CausalScope, Comparison, TreatmentIdentity
from armproof.evidence.checksums import checksum_ledger_paths, verify_checksum_ledger
from armproof.evidence.checksums import ChecksumResult
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
from armproof.policy import decision_to_dict
from armproof.profiling import parse_perf_attribution
from armproof.quality import compare_quality, evaluate_quality, load_quality_cases
from armproof.evidence.sustained_audit import derive_sustained_audit
from armproof.workload import SloPolicy, load_requests_jsonl, summarize_samples


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
        binding = _require_performix_binding(profile, verified.comparison)
        _require_aws_graviton_binding(binding)
        summary = {**dict(verified.summary), "performix": profile}
        return VerifiedEvidence(
            comparison=verified.comparison,
            summary=MappingProxyType(summary),
            checksums=verified.checksums,
            reproduction_checksums=verified.reproduction_checksums,
            performix=MappingProxyType(profile),
            adapter=verified.adapter,
        )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _derived_identity(
    payload: Mapping[str, Any],
    treatment_id: str,
    root: Path,
    ledger_paths: set[str],
) -> TreatmentIdentity:
    required = {"treatment_id", "sources", "controls"}
    if (
        not isinstance(payload, Mapping)
        or set(payload) != required
        or payload.get("treatment_id") != treatment_id
    ):
        raise ValueError(f"observed identity is invalid: {treatment_id}")
    sources = payload["sources"]
    source_names = {"artifact", "runtime", "workload", "environment"}
    if not isinstance(sources, Mapping) or set(sources) != source_names:
        raise ValueError(f"observed identity sources are invalid: {treatment_id}")
    if not isinstance(payload["controls"], Mapping):
        raise ValueError(f"observed identity fields are invalid: {treatment_id}")
    paths = {
        name: _bound_file(
            root,
            root / str(sources[name]),
            ledger_paths,
            f"{treatment_id} {name} identity source",
        )
        for name in source_names
    }
    return TreatmentIdentity(
        treatment_id=treatment_id,
        artifact_sha256=_sha256(paths["artifact"]),
        runtime_sha256=_sha256(paths["runtime"]),
        workload_sha256=_sha256(paths["workload"]),
        environment_sha256=_sha256(paths["environment"]),
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


def _command_sha256(command: tuple[str, ...]) -> str:
    payload = json.dumps(list(command), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_http_slo_claims(contract: Contract, comparison_id: str) -> None:
    required_metrics = {
        "capacity_ratio_lower_bound",
        "arm_path_treatment_observed",
        "accuracy_delta_pp",
        "macro_f1_delta_pp",
        "schema_valid_rate",
    }
    claims_by_metric: dict[str, list[Any]] = {}
    for claim in contract.claims:
        claims_by_metric.setdefault(claim.metric, []).append(claim)
    missing = required_metrics - set(claims_by_metric)
    invalid = {
        metric
        for metric in required_metrics - missing
        if len(claims_by_metric[metric]) != 1
        or not claims_by_metric[metric][0].required
        or claims_by_metric[metric][0].comparison_id != comparison_id
        or claims_by_metric[metric][0].causal_scope is not CausalScope.ARM_ACCELERATION
    }
    quality_metrics = {"accuracy_delta_pp", "macro_f1_delta_pp", "schema_valid_rate"}
    capacity = claims_by_metric.get("capacity_ratio_lower_bound", [])
    quality_claim_ids = {
        claims_by_metric[metric][0].claim_id
        for metric in quality_metrics
        if len(claims_by_metric.get(metric, [])) == 1
    }
    shape = {
        "capacity_ratio_lower_bound": ("gte", {"request_samples", "boundary_confirmations"}),
        "arm_path_treatment_observed": ("eq", {"arm_callchains"}),
        "accuracy_delta_pp": ("gte", {"quality_rows", "workload_manifest"}),
        "macro_f1_delta_pp": ("gte", {"quality_rows", "workload_manifest"}),
        "schema_valid_rate": ("gte", {"quality_rows", "workload_manifest"}),
    }
    malformed = set()
    for metric, (operator, evidence) in shape.items():
        rows = claims_by_metric.get(metric, [])
        if len(rows) == 1 and (
            rows[0].operator != operator
            or not evidence.issubset(rows[0].required_evidence)
        ):
            malformed.add(metric)
    if len(claims_by_metric.get("arm_path_treatment_observed", [])) == 1 and (
        claims_by_metric["arm_path_treatment_observed"][0].threshold != 1.0
    ):
        malformed.add("arm_path_treatment_observed")
    if len(claims_by_metric.get("capacity_ratio_lower_bound", [])) == 1 and (
        claims_by_metric["capacity_ratio_lower_bound"][0].threshold <= 1.0
    ):
        malformed.add("capacity_ratio_lower_bound")
    for metric in ("accuracy_delta_pp", "macro_f1_delta_pp"):
        rows = claims_by_metric.get(metric, [])
        if len(rows) == 1 and rows[0].threshold < -5.0:
            malformed.add(metric)
    schema_rows = claims_by_metric.get("schema_valid_rate", [])
    if len(schema_rows) == 1 and not (0.95 <= schema_rows[0].threshold <= 1.0):
        malformed.add("schema_valid_rate")
    if missing or invalid or malformed or not capacity or not quality_claim_ids.issubset(
        set(capacity[0].depends_on)
    ):
        raise ValueError(
            "HTTP SLO contract requires required quality claims, Arm attribution, "
            "a real capacity gain, and a quality-dependent capacity claim with "
            "no more than five percentage points of classification loss"
        )


def _require_performix_binding(
    profile: Mapping[str, Any], comparison: Comparison
) -> Mapping[str, Any]:
    binding = profile.get("identity_binding")
    if not isinstance(binding, Mapping):
        raise ValueError("Performix archive lacks release identity bindings")
    matched_environment = binding.get("matched_environment")
    machine = binding.get("machine")
    expected_threads = str(
        comparison.baseline.controls.get(
            "threads", comparison.baseline.controls.get("intra_op_num_threads", "")
        )
    )
    if (
        binding.get("runtime_sha256") != comparison.baseline.runtime_sha256
        or binding.get("runtime_sha256") != comparison.treatment.runtime_sha256
        or not isinstance(binding.get("model_ref"), str)
        or not binding["model_ref"]
        or not isinstance(binding.get("workload_ref"), str)
        or not binding["workload_ref"]
        or not isinstance(binding.get("environment_ref"), str)
        or not binding["environment_ref"]
        or not isinstance(matched_environment, Mapping)
        or not isinstance(machine, Mapping)
        or machine.get("architecture") not in {"aarch64", "arm64"}
        or not isinstance(machine.get("cpu_count"), int)
        or machine["cpu_count"] < 1
        or not isinstance(binding.get("uname"), str)
        or not any(token in binding["uname"] for token in ("aarch64", "arm64"))
        or not expected_threads
        or matched_environment.get("OMP_NUM_THREADS") != expected_threads
    ):
        raise ValueError(
            "Performix runtime, workload, or environment does not match the comparison"
        )
    return binding


def _require_aws_graviton_binding(binding: Mapping[str, Any]) -> None:
    machine = binding.get("machine")
    if (
        not isinstance(machine, Mapping)
        or machine.get("bios_vendor_id") != "AWS"
        or "AWS Graviton" not in str(machine.get("bios_model_name"))
        or not str(machine.get("model_name", "")).startswith("Neoverse-")
    ):
        raise ValueError("Performix machine is not an observed AWS Graviton host")


def _validate_measurement_cadence(
    samples: list[Any], seconds: float, field: str
) -> None:
    if len(samples) < 2:
        raise ValueError(f"HTTP SLO measurement cadence needs at least two rows: {field}")
    for sample in samples:
        timestamps = (sample.scheduled_ns, sample.started_ns, sample.finished_ns)
        if not all(isinstance(value, int) and not isinstance(value, bool) for value in timestamps):
            raise ValueError(f"HTTP SLO measurement cadence has non-integer timestamps: {field}")
        if not (0 <= sample.scheduled_ns <= sample.started_ns <= sample.finished_ns):
            raise ValueError(f"HTTP SLO measurement cadence has unordered timestamps: {field}")
    scheduled = [sample.scheduled_ns for sample in samples]
    if scheduled != sorted(scheduled) or len(scheduled) != len(set(scheduled)):
        raise ValueError(f"HTTP SLO measurement cadence is not strictly increasing: {field}")
    expected_interval = seconds * 1_000_000_000 / len(samples)
    tolerance = max(1_000_000.0, expected_interval * 0.05)
    intervals = [right - left for left, right in zip(scheduled, scheduled[1:])]
    if any(abs(interval - expected_interval) > tolerance for interval in intervals):
        raise ValueError(f"HTTP SLO measurement cadence disagrees with declared duration: {field}")


def _end_to_end_samples(samples: list[Any]) -> list[Any]:
    """Include client-side dispatch delay in the fixed-SLO latency."""
    return [replace(sample, started_ns=sample.scheduled_ns) for sample in samples]


def _verify_workload_manifest(
    path: Path,
    capacity_workload: Path,
    quality_workload: Path,
) -> None:
    manifest = _json(path)
    expected = {
        "schema_version", "capacity_workload_sha256", "quality_workload_sha256"
    }
    if set(manifest) != expected or manifest.get("schema_version") != "1.0.0":
        raise ValueError("HTTP SLO workload manifest is invalid")
    observed = {
        "capacity_workload_sha256": _sha256(capacity_workload),
        "quality_workload_sha256": _sha256(quality_workload),
    }
    if any(manifest[name] != digest for name, digest in observed.items()):
        raise ValueError("HTTP SLO workload manifest hash mismatch")


def _verify_profile_manifest(
    root: Path,
    ledger_paths: set[str],
    attribution: Mapping[str, Any],
    identities: Mapping[str, TreatmentIdentity],
    declarations: Mapping[str, Any],
) -> None:
    manifest_path = _bound_file(
        root, root / str(attribution["profile_manifest"]), ledger_paths,
        "profile manifest",
    )
    manifest = _json(manifest_path)
    if set(manifest) != {"schema_version", "profiler", "event", "runs"} or (
        manifest.get("schema_version") != "1.0.0"
        or manifest.get("profiler") != "linux-perf"
        or manifest.get("event") != "cycles:P"
    ):
        raise ValueError("HTTP SLO profile manifest is invalid")
    runs = manifest.get("runs")
    if not isinstance(runs, Mapping) or set(runs) != {"baseline", "treatment"}:
        raise ValueError("HTTP SLO profile manifest runs are invalid")
    fields = {
        "treatment_id", "report", "report_sha256", "command_sha256", "artifact_sha256",
        "runtime_sha256", "workload_sha256", "environment_sha256", "controls",
    }
    for lane in ("baseline", "treatment"):
        run = runs[lane]
        identity = identities[lane]
        declaration = declarations[identity.treatment_id]
        if not isinstance(run, Mapping) or set(run) != fields:
            raise ValueError(f"HTTP SLO {lane} profile manifest is invalid")
        report = _bound_file(
            root, root / str(run["report"]), ledger_paths, f"{lane} profile report"
        )
        expected_values = {
            "treatment_id": identity.treatment_id,
            "report": str(attribution[f"{lane}_profile"]),
            "report_sha256": _sha256(report),
            "command_sha256": _command_sha256(declaration.command),
            "artifact_sha256": identity.artifact_sha256,
            "runtime_sha256": identity.runtime_sha256,
            "workload_sha256": identity.workload_sha256,
            "environment_sha256": identity.environment_sha256,
        }
        if any(run.get(name) != value for name, value in expected_values.items()) or (
            run.get("controls") != dict(identity.controls)
        ):
            raise ValueError(f"HTTP SLO {lane} profile manifest hash mismatch")


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
        if not ledger.is_file():
            raise ValueError(
                "No measured evidence found. Complete ADOPTION_CHECKLIST.md, "
                "place the collected files under evidence/, generate "
                "evidence/SHA256SUMS, then rerun armproof ci."
            )
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
            "arm_attribution", "identity_manifest", "capacity_workload", "quality",
        }
        if set(protocol) != expected or protocol["schema_version"] != "1.0.0":
            raise ValueError("HTTP SLO protocol has unsupported fields or schema")
        seconds = float(protocol["measurement_seconds"])
        minimum_rows = int(protocol["minimum_requests_per_file"])
        if seconds <= 0 or minimum_rows < 2:
            raise ValueError("HTTP SLO measurement requirements are invalid")
        _validate_http_slo_claims(contract, str(protocol["comparison_id"]))
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
        observed_paths: set[Path] = set()
        observed_digests: set[str] = set()
        for name in ("baseline", "treatment"):
            outcomes = boundary_config[name]
            if not isinstance(outcomes, Mapping) or set(outcomes) != {"pass", "fail"}:
                raise ValueError(f"HTTP SLO {name} requires pass and fail files")
            for outcome in ("pass", "fail"):
                paths = outcomes[outcome]
                if not isinstance(paths, list) or len(paths) < 3:
                    raise ValueError("each HTTP SLO boundary requires at least three files")
                resolved_paths = [
                    (root / str(relative)).resolve() for relative in paths
                ]
                if len(resolved_paths) != len(set(resolved_paths)):
                    raise ValueError("each HTTP SLO boundary requires distinct confirmation files")
                for relative in paths:
                    confirmation_path = _bound_file(
                        root,
                        root / str(relative),
                        ledger_paths,
                        f"{name}.{outcome} boundary",
                    )
                    digest = _sha256(confirmation_path)
                    if confirmation_path in observed_paths or digest in observed_digests:
                        raise ValueError(
                            "HTTP SLO boundaries require independent, distinct confirmation files"
                        )
                    observed_paths.add(confirmation_path)
                    observed_digests.add(digest)
                    samples = _samples(confirmation_path)
                    if len(samples) < minimum_rows:
                        raise ValueError(
                            f"HTTP SLO boundary has fewer than {minimum_rows} requests: {relative}"
                        )
                    _validate_measurement_cadence(
                        samples, seconds, f"{name}.{outcome}:{relative}"
                    )
                    minimum_observed = (
                        len(samples) if minimum_observed is None
                        else min(minimum_observed, len(samples))
                    )
                    summary = summarize_samples(_end_to_end_samples(samples), seconds)
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
            "baseline_profile", "treatment_profile", "profile_manifest", "symbol_regex"
        }:
            raise ValueError("HTTP SLO Arm attribution config is invalid")
        pattern = str(attribution["symbol_regex"])
        re.compile(pattern)
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
        baseline_attribution = parse_perf_attribution(
            baseline_profile.read_text(encoding="utf-8", errors="replace"), pattern
        )
        treatment_attribution = parse_perf_attribution(
            treatment_profile.read_text(encoding="utf-8", errors="replace"), pattern
        )
        for name, observed in (
            ("baseline", baseline_attribution),
            ("treatment", treatment_attribution),
        ):
            if observed.event != "cycles:P" or observed.samples < 100:
                raise ValueError(f"HTTP SLO {name} profile lacks sampled cycles")
            if observed.lost_samples != 0:
                raise ValueError(f"HTTP SLO {name} profile contains lost samples")
        baseline_arm = baseline_attribution.maximum_children_share > 0
        treatment_arm = treatment_attribution.maximum_children_share > 0
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
        quality = protocol["quality"]
        if not isinstance(quality, Mapping) or set(quality) != {
            "workload", "baseline_samples", "treatment_samples"
        }:
            raise ValueError("HTTP SLO quality config is invalid")
        quality_workload = _bound_file(
            root, root / str(quality["workload"]), ledger_paths, "quality workload"
        )
        capacity_workload = _bound_file(
            root,
            root / str(protocol["capacity_workload"]),
            ledger_paths,
            "capacity workload",
        )
        load_requests_jsonl(capacity_workload)
        cases = load_quality_cases(quality_workload)
        expected_labels = {
            case.request.request_id: case.expected_intent for case in cases
        }
        quality_paths = {
            field: _bound_file(
                root, root / str(quality[field]), ledger_paths, f"quality {field}"
            )
            for field in ("baseline_samples", "treatment_samples")
        }
        if (
            quality_paths["baseline_samples"].resolve()
            == quality_paths["treatment_samples"].resolve()
            or _sha256(quality_paths["baseline_samples"])
            == _sha256(quality_paths["treatment_samples"])
        ):
            raise ValueError(
                "HTTP SLO quality evidence must use distinct lane artifacts and digests"
            )
        quality_results = []
        for field in ("baseline_samples", "treatment_samples"):
            sample_path = quality_paths[field]
            result = evaluate_quality(cases, _samples(sample_path))
            labels = {row.request_id: row.expected_intent for row in result.rows}
            if labels != expected_labels:
                raise ValueError("HTTP SLO quality rows do not match the workload")
            quality_results.append(result)
        quality_comparison = compare_quality(*quality_results)

        baseline_identity = _derived_identity(
            identities["baseline"], str(protocol["baseline_treatment_id"]),
            root, ledger_paths,
        )
        treatment_identity = _derived_identity(
            identities["treatment"], str(protocol["treatment_treatment_id"]),
            root, ledger_paths,
        )
        declarations = {row.treatment_id: row for row in contract.treatments}
        for identity in (baseline_identity, treatment_identity):
            declaration = declarations.get(identity.treatment_id)
            if declaration is None or dict(declaration.environment) != dict(identity.controls):
                raise ValueError(
                    f"HTTP SLO observed controls do not match the contract: "
                    f"{identity.treatment_id}"
                )

        identity_index = {
            "baseline": baseline_identity,
            "treatment": treatment_identity,
        }
        for lane in ("baseline", "treatment"):
            source = identities[lane]["sources"]["workload"]
            manifest_path = _bound_file(
                root,
                root / str(source),
                ledger_paths,
                f"{lane} workload identity source",
            )
            _verify_workload_manifest(
                manifest_path, capacity_workload, quality_workload
            )
        _verify_profile_manifest(
            root, ledger_paths, attribution, identity_index, declarations
        )

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
            "accuracy_delta_pp": quality_comparison.accuracy_delta_pp,
            "macro_f1_delta_pp": quality_comparison.macro_f1_delta_pp,
            "schema_valid_rate": quality_comparison.schema_valid_rate,
            "prediction_agreement": quality_comparison.prediction_agreement,
            "enabled_arm_cycle_share": treatment_attribution.maximum_children_share,
            "lost_perf_samples": float(
                baseline_attribution.lost_samples + treatment_attribution.lost_samples
            ),
        }
        comparison = Comparison(
            comparison_id=str(protocol["comparison_id"]),
            causal_scope=next(iter(scopes)),
            baseline=baseline_identity,
            treatment=treatment_identity,
            metrics=MappingProxyType(metrics),
            evidence_kinds=frozenset({
                "request_samples", "boundary_confirmations", "artifact_hashes",
                "arm_callchains", "quality_rows", "workload_manifest",
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
            "quality_comparison": asdict(quality_comparison),
        }
        return VerifiedEvidence(
            comparison=comparison,
            summary=MappingProxyType(summary),
            checksums=checksums,
            reproduction_checksums=None,
            adapter=self.adapter_id,
        )


class KleidiAISustainedAdapter:
    """Derive the EXP-2026-009 conservative release decision from its archive."""

    adapter_id = "kleidiai-sustained-v1"

    def verify(
        self, contract: Contract, config: Mapping[str, Any], base: Path
    ) -> VerifiedEvidence:
        fields = {
            "adapter", "archive", "archive_sha256", "workload_manifest", "performix"
        }
        _exact_config(config, fields, self.adapter_id)
        archive_sha256 = config.get("archive_sha256")
        if (
            not isinstance(archive_sha256, str)
            or len(archive_sha256) != 64
            or any(char not in "0123456789abcdef" for char in archive_sha256)
        ):
            raise ValueError("sustained archive_sha256 must be a lowercase SHA-256")
        audit = derive_sustained_audit(
            _path(base, config["archive"], "archive"),
            expected_sha256=archive_sha256,
            contract=contract,
            workload_manifest=_path(
                base, config["workload_manifest"], "workload_manifest"
            ),
        )
        performix = config["performix"]
        if not isinstance(performix, Mapping) or set(performix) != PERFORMIX_CONFIG_FIELDS:
            raise ValueError(
                "sustained adapter performix requires exactly "
                f"{sorted(PERFORMIX_CONFIG_FIELDS)}"
            )
        configured_perf_share = float(performix["linux_perf_kai_cycle_share"])
        if not math.isclose(
            configured_perf_share,
            audit.enabled_kai_cycle_share,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            raise ValueError(
                "configured Linux perf share disagrees with the sustained archive"
            )
        performix_profile = verify_performix_archive(
            _path(base, performix["archive"], "performix.archive"),
            expected_archive_sha256=str(performix["archive_sha256"]),
            expected_experiment_id=str(performix["experiment_id"]),
            disabled_run_id=str(performix["disabled_run_id"]),
            enabled_run_id=str(performix["enabled_run_id"]),
            linux_perf_share=audit.enabled_kai_cycle_share,
            maximum_share_difference=float(performix["maximum_share_difference"]),
        )
        binding = _require_performix_binding(performix_profile, audit.comparison)
        expected_threads = str(audit.comparison.baseline.controls["threads"])
        matched_environment = binding.get("matched_environment")
        machine = binding.get("machine")
        if (
            binding.get("runtime_sha256")
            != audit.comparison.baseline.runtime_sha256
            or binding.get("workload_ref")
            != "data/banking77/generated/traffic-mixed.jsonl"
            or "c8g.4xlarge" not in str(binding.get("environment_ref"))
            or not isinstance(matched_environment, Mapping)
            or matched_environment.get("OMP_NUM_THREADS") != expected_threads
            or not isinstance(machine, Mapping)
            or machine.get("architecture") != "aarch64"
            or machine.get("cpu_count") != 16
            or machine.get("bios_vendor_id") != "AWS"
            or "AWS Graviton4" not in str(machine.get("bios_model_name"))
            or machine.get("model_name") != "Neoverse-V2"
        ):
            raise ValueError(
                "Performix runtime, workload, or environment does not match the release comparison"
            )

        def trial_row(
            treatment: str,
            boundary: str,
            rate: float,
            passed: tuple[bool, ...],
            p95_ms: tuple[float, ...],
        ) -> dict[str, Any]:
            return {
                "treatment": treatment,
                "boundary": boundary,
                "rate_rps": rate,
                "outcomes": ["pass" if outcome else "fail" for outcome in passed],
                "p95_ms": list(p95_ms),
            }

        trial_matrix = [
            trial_row(
                "KleidiAI disabled", "known sustainable", audit.baseline_pass_rps,
                audit.baseline_pass_trial_passed, audit.baseline_pass_p95_ms,
            ),
            trial_row(
                "KleidiAI disabled", "first failing probe", audit.baseline_fail_rps,
                audit.baseline_fail_probe_trial_passed,
                audit.baseline_fail_probe_p95_ms,
            ),
            trial_row(
                "KleidiAI enabled", "known sustainable", audit.treatment_pass_rps,
                audit.treatment_pass_trial_passed, audit.treatment_pass_p95_ms,
            ),
            trial_row(
                "KleidiAI enabled", "next probe", audit.treatment_fail_rps,
                audit.treatment_fail_probe_trial_passed,
                audit.treatment_fail_probe_p95_ms,
            ),
        ]
        summary = {
            "schema_version": "1.0.0",
            "adapter": self.adapter_id,
            "experiment_id": audit.experiment_id,
            "passed": audit.decision.passed,
            "archive_sha256": audit.archive_sha256,
            "internal_checksummed_files": audit.internal_checksummed_files,
            "raw_confirmation_files": audit.raw_confirmation_files,
            "raw_confirmation_samples": audit.raw_confirmation_samples,
            "confirmation_seconds": audit.confirmation_seconds,
            "matched_control_verified": audit.matched_control_verified,
            "only_changed_control": audit.only_changed_control,
            "minimum_capacity_ratio": audit.minimum_capacity_ratio,
            "tested_pass_point_ratio": audit.tested_pass_point_ratio,
            "capacity_display": {
                "description": (
                    "Conservative lower bound from the optimized known-sustainable "
                    "rate divided by the baseline first-failing probe."
                ),
                "baseline_label": "Baseline fail",
                "treatment_label": "Optimized pass",
            },
            "mixes": {
                "mixed": {
                    "valid_boundary_confirmations": True,
                    "disabled_boundary": [
                        audit.baseline_pass_rps, audit.baseline_fail_rps
                    ],
                    "enabled_boundary": [
                        audit.treatment_pass_rps, audit.treatment_fail_rps
                    ],
                    "ratio": {
                        "baseline_median": audit.baseline_fail_rps,
                        "treatment_median": audit.treatment_pass_rps,
                        "ratio": audit.minimum_capacity_ratio,
                    },
                }
            },
            "trial_matrix": trial_matrix,
            "quality_comparison": {
                "accuracy_delta_pp": audit.accuracy_delta_pp,
                "macro_f1_delta_pp": audit.macro_f1_delta_pp,
                "schema_valid_rate": audit.schema_valid_rate,
            },
            "arm_attribution": {
                "disabled_kai_cycle_share": audit.disabled_kai_cycle_share,
                "enabled_kai_cycle_share": audit.enabled_kai_cycle_share,
                "lost_perf_samples": audit.lost_perf_samples,
            },
            "decision": decision_to_dict(audit.decision),
        }
        return VerifiedEvidence(
            comparison=audit.comparison,
            summary=MappingProxyType(summary),
            checksums=ChecksumResult(
                checked=audit.internal_checksummed_files,
                missing=(),
                mismatched=(),
            ),
            reproduction_checksums=None,
            performix=MappingProxyType(performix_profile),
            adapter=self.adapter_id,
        )


BUILTIN_ADAPTERS: dict[str, EvidenceAdapter] = {
    ADAPTER_ID: KleidiAICapacityAdapter(),
    HttpSloAdapter.adapter_id: HttpSloAdapter(),
    KleidiAISustainedAdapter.adapter_id: KleidiAISustainedAdapter(),
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
