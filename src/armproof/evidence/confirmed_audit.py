"""Derive a preregistered identity-bound capacity claim from raw evidence."""

from __future__ import annotations

import hashlib
import json
import math
import tarfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

from armproof.contracts import Contract, validate_comparison_identities
from armproof.domain import CausalScope, Comparison, Decision, TreatmentIdentity
from armproof.policy import evaluate_claims
from armproof.profiling import parse_perf_attribution
from armproof.quality import QualityResult, compare_quality, quality_from_dict, quality_to_dict
from armproof.workload import RequestSample, SloPolicy, load_requests_jsonl, summarize_samples
from armproof.workload.io import summary_to_dict


@dataclass(frozen=True)
class ConfirmedCapacityAudit:
    experiment_id: str
    archive_sha256: str
    passed: bool
    baseline_failing_rps: float
    treatment_passing_rps: float
    minimum_capacity_ratio: float
    confirmation_seconds: int
    confirmations_per_treatment: int
    baseline_failures: int
    treatment_passes: int
    baseline_p95_ms: tuple[float, ...]
    treatment_p95_ms: tuple[float, ...]
    baseline_max_dispatch_ms: tuple[float, ...]
    treatment_max_dispatch_ms: tuple[float, ...]
    raw_confirmation_files: int
    raw_confirmation_samples: int
    raw_quality_outputs: int
    accuracy_delta_pp: float
    macro_f1_delta_pp: float
    schema_valid_rate: float
    matched_control_verified: bool
    internal_checksummed_files: int
    disabled_kai_cycle_share: float
    enabled_kai_cycle_share: float
    lost_perf_samples: int
    comparison: Comparison
    decision: Decision


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_confirmed_contract_claims(
    contract: Contract,
    *,
    experiment_id: str,
    acceptance: Mapping[str, Any],
    protocol: Mapping[str, Any],
    performix_acceptance: Mapping[str, Any],
    raw_quality_output_count: int,
) -> None:
    """Bind every release claim to the frozen experiment and profiler plans."""
    plan_pairs = {
        "control_rate_rps": "baseline_failing_rps",
        "treatment_rate_rps": "treatment_passing_rps",
        "confirmations_per_treatment": "confirmations",
        "confirmation_seconds": "confirmation_seconds",
        "maximum_p95_ms": "p95_slo_ms",
        "maximum_error_rate": "max_error_rate",
        "minimum_delivery_ratio": "minimum_delivery_ratio",
        "minimum_requests_per_confirmation": "minimum_confirmation_requests",
        "minimum_capacity_ratio": "minimum_capacity_ratio",
        "maximum_quality_loss_pp": "maximum_quality_loss_pp",
        "minimum_schema_valid_rate": "minimum_schema_valid_rate",
    }
    for acceptance_field, protocol_field in plan_pairs.items():
        if acceptance_field not in acceptance or protocol_field not in protocol:
            raise ValueError("confirmation plans omit a required release threshold")
        if not math.isclose(
            float(acceptance[acceptance_field]),
            float(protocol[protocol_field]),
            rel_tol=0,
            abs_tol=1e-12,
        ):
            raise ValueError(
                f"confirmation protocol {protocol_field} differs from preregistration"
            )
    comparison_id = f"{experiment_id.lower()}-confirmed"
    confirmations = int(protocol["confirmations"])
    seconds = float(protocol["confirmation_seconds"])
    expected_request_count = confirmations * (
        round(float(protocol["baseline_failing_rps"]) * seconds)
        + round(float(protocol["treatment_passing_rps"]) * seconds)
    )
    common_quality = frozenset({
        "quality_rows", "raw_model_outputs", "artifact_hashes",
        "performix_code_hotspots",
    })
    expected = {
        "quality-accuracy": (
            "accuracy_delta_pp", "gte", -float(acceptance["maximum_quality_loss_pp"]),
            common_quality, (),
        ),
        "quality-macro-f1": (
            "macro_f1_delta_pp", "gte", -float(acceptance["maximum_quality_loss_pp"]),
            common_quality, (),
        ),
        "quality-schema": (
            "schema_valid_rate", "gte", float(acceptance["minimum_schema_valid_rate"]),
            common_quality, (),
        ),
        "sustained-capacity-lower-bound": (
            "minimum_capacity_ratio", "gte", float(protocol["minimum_capacity_ratio"]),
            frozenset({
                "request_samples", "boundary_confirmations", "artifact_hashes",
                "performix_code_hotspots",
            }),
            ("quality-accuracy", "quality-macro-f1", "quality-schema"),
        ),
        "sustained-window-count": (
            "raw_confirmation_files", "gte", float(confirmations * 2),
            frozenset({"request_samples", "boundary_confirmations", "artifact_hashes"}), (),
        ),
        "sustained-request-count": (
            "raw_confirmation_samples", "gte", float(expected_request_count),
            frozenset({"request_samples", "boundary_confirmations", "artifact_hashes"}), (),
        ),
        "raw-quality-output-count": (
            "raw_quality_outputs", "eq", float(raw_quality_output_count),
            frozenset({"quality_rows", "raw_model_outputs", "artifact_hashes"}), (),
        ),
        "arm-control-zero": (
            "performix_disabled_kai_share", "eq", 0.0,
            frozenset({"performix_code_hotspots", "artifact_hashes"}), (),
        ),
        "arm-treatment-share": (
            "performix_enabled_kai_share", "gte",
            float(performix_acceptance["minimum_enabled_kai_sample_share"]),
            frozenset({"performix_code_hotspots", "artifact_hashes"}),
            ("arm-control-zero",),
        ),
        "performix-sample-count": (
            "performix_minimum_profile_samples", "gte",
            float(performix_acceptance["minimum_total_function_samples_per_treatment"]),
            frozenset({"performix_code_hotspots", "artifact_hashes"}),
            ("arm-control-zero",),
        ),
    }
    if contract.contract_id != "phi4-graviton-kleidiai-confirmed-release":
        raise ValueError("confirmation contract id differs from the frozen release")
    actual = {claim.claim_id: claim for claim in contract.claims}
    if set(actual) != set(expected):
        raise ValueError("confirmation contract claim set differs from the frozen plans")
    for claim_id, (metric, operator, threshold, evidence, dependencies) in expected.items():
        claim = actual[claim_id]
        matches = (
            claim.causal_scope is CausalScope.ARM_ACCELERATION
            and claim.comparison_id == comparison_id
            and claim.metric == metric
            and claim.operator == operator
            and math.isclose(claim.threshold, threshold, rel_tol=0, abs_tol=1e-12)
            and claim.required_evidence == evidence
            and claim.required is True
            and claim.depends_on == dependencies
        )
        if not matches:
            raise ValueError(
                f"confirmation contract claim {claim_id} differs from the frozen plans"
            )


def _text(archive: tarfile.TarFile, name: str) -> str:
    member = archive.getmember(name)
    stream = archive.extractfile(member)
    if not member.isfile() or stream is None:
        raise ValueError(f"confirmation archive member is not a file: {name}")
    return stream.read().decode("utf-8")


def _json(archive: tarfile.TarFile, name: str) -> Any:
    return json.loads(_text(archive, name))


def _verify_internal_checksums(archive: tarfile.TarFile) -> int:
    prefix = "/opt/armproof/evidence/"
    checked: set[str] = set()
    for line in _text(archive, "evidence/SHA256SUMS").splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64 or not parts[1].startswith(prefix):
            raise ValueError("confirmation archive contains an invalid checksum entry")
        expected, original = parts
        relative = original.removeprefix(prefix)
        if not relative or relative in checked or ".." in Path(relative).parts:
            raise ValueError("confirmation archive contains an unsafe checksum path")
        member = archive.getmember(f"evidence/{relative}")
        stream = archive.extractfile(member)
        if not member.isfile() or stream is None:
            raise ValueError("confirmation checksum entry is not a regular file")
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ValueError(f"confirmation checksum mismatch: {relative}")
        checked.add(relative)
    if not checked:
        raise ValueError("confirmation checksum ledger is empty")
    return len(checked)


def _verify_matched_control(archive: tarfile.TarFile) -> tuple[bool, int]:
    configs = {
        lane: _json(
            archive,
            f"evidence/capacity/variants/{lane}/genai_config.json",
        )
        for lane in ("disabled", "enabled")
    }
    sessions = {
        lane: configs[lane]["model"]["decoder"]["session_options"]
        for lane in configs
    }
    if sessions["disabled"].get("mlas.disable_kleidiai") != "1":
        return False, 0
    if sessions["enabled"].get("mlas.disable_kleidiai") != "0":
        return False, 0
    threads = int(sessions["disabled"]["intra_op_num_threads"])
    if int(sessions["enabled"]["intra_op_num_threads"]) != threads:
        return False, threads
    sessions["disabled"]["mlas.disable_kleidiai"] = "0"
    if configs["disabled"] != configs["enabled"]:
        return False, threads

    members: dict[str, dict[str, tarfile.TarInfo]] = {}
    for lane in ("disabled", "enabled"):
        prefix = f"evidence/capacity/variants/{lane}/"
        members[lane] = {
            member.name.removeprefix(prefix): member
            for member in archive.getmembers()
            if member.name.startswith(prefix)
            and member.name.rstrip("/") != prefix.rstrip("/")
        }
    if set(members["disabled"]) != set(members["enabled"]):
        return False, threads
    source_identity_name = "armproof_source_identity.json"
    if source_identity_name in members["disabled"]:
        if _json(
            archive,
            f"evidence/capacity/variants/disabled/{source_identity_name}",
        ) != _json(
            archive,
            f"evidence/capacity/variants/enabled/{source_identity_name}",
        ):
            return False, threads
    for relative in set(members["disabled"]) - {
        "genai_config.json", source_identity_name,
    }:
        disabled = members["disabled"][relative]
        enabled = members["enabled"][relative]
        if not (
            disabled.issym()
            and enabled.issym()
            and disabled.linkname == enabled.linkname
        ):
            return False, threads
    return True, threads


def _parse_samples(
    text: str,
    *,
    treatment_id: str,
    repetition: int,
    source_ids: tuple[str, ...],
) -> list[RequestSample]:
    rows: list[RequestSample] = []
    seen: set[str] = set()
    required = {
        "request_id", "scheduled_ns", "started_ns", "finished_ns", "latency_ms",
        "status_code", "error", "response",
    }
    for index, line in enumerate(text.splitlines()):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError("confirmation request row has an invalid schema")
        source_id = source_ids[index % len(source_ids)]
        expected_id = f"confirm-{repetition}-{treatment_id}-{index:06d}-{source_id}"
        if row["request_id"] != expected_id or expected_id in seen:
            raise ValueError("confirmation request sequence is invalid")
        response = row["response"]
        succeeded = (
            row["status_code"] == 200
            and row["error"] is None
            and isinstance(response, dict)
            and response.get("backend") == treatment_id
            and response.get("request_id") == source_id
        )
        timed_out = (
            row["status_code"] is None
            and row["error"] == "TimeoutError"
            and response is None
        )
        if not (succeeded or timed_out):
            raise ValueError("confirmation response is not attributed to its treatment")
        scheduled = int(row["scheduled_ns"])
        started = int(row["started_ns"])
        finished = int(row["finished_ns"])
        if not scheduled <= started <= finished:
            raise ValueError("confirmation timestamps are invalid")
        latency_ms = (finished - started) / 1_000_000
        if not math.isclose(float(row["latency_ms"]), latency_ms, abs_tol=1e-9):
            raise ValueError("confirmation latency does not match timestamps")
        seen.add(expected_id)
        rows.append(RequestSample(
            expected_id,
            scheduled,
            started,
            finished,
            row["status_code"],
            row["error"],
            response,
        ))
    if not rows:
        raise ValueError("confirmation request file is empty")
    schedules = [row.scheduled_ns for row in rows]
    if schedules != sorted(set(schedules)):
        raise ValueError("confirmation schedule is not strictly ordered")
    return rows


def _end_to_end_samples(
    samples: list[RequestSample], *, duration_seconds: float, slo_ms: float
) -> tuple[list[RequestSample], float]:
    """Include client dispatch delay and reject responses outside the SLO drain."""
    if not samples:
        raise ValueError("confirmation request file is empty")
    deadline_ns = samples[0].scheduled_ns + int(
        (duration_seconds + slo_ms / 1000) * 1_000_000_000
    )
    maximum_dispatch_ms = max(
        (sample.started_ns - sample.scheduled_ns) / 1_000_000
        for sample in samples
    )
    adjusted = [
        replace(
            sample,
            started_ns=sample.scheduled_ns,
            error=(
                sample.error
                if sample.finished_ns <= deadline_ns
                else "completion_after_slo_drain"
            ),
        )
        for sample in samples
    ]
    return adjusted, maximum_dispatch_ms


def _verify_response_identities(
    samples: list[RequestSample],
    *,
    treatment_id: str,
    source_artifact_sha256: str,
    threads: int,
) -> tuple[set[str], set[str]]:
    model_identities: set[str] = set()
    runtime_versions: set[str] = set()
    expected_control = "1" if treatment_id == "kleidiai-disabled" else "0"
    for sample in samples:
        response = sample.response
        if response is None and sample.status_code is None and sample.error == "TimeoutError":
            continue
        identity = response.get("runtime_identity") if isinstance(response, Mapping) else None
        if not isinstance(identity, Mapping):
            raise ValueError("confirmation response is missing its runtime identity")
        model_identity = identity.get("model_identity")
        runtime_version = identity.get("runtime_version")
        if (
            not isinstance(model_identity, str)
            or len(model_identity) != 64
            or any(character not in "0123456789abcdef" for character in model_identity)
            or not isinstance(runtime_version, str)
            or not runtime_version
            or identity.get("source_artifact_sha256") != source_artifact_sha256
            or identity.get("runtime") != "onnxruntime-genai"
            or identity.get("threads") != threads
            or identity.get("architecture") not in {"aarch64", "arm64"}
            or identity.get("cpu_affinity") != list(range(threads))
            or identity.get("optimization_control")
            != {"mlas.disable_kleidiai": expected_control}
        ):
            raise ValueError("confirmation response runtime identity is inconsistent")
        model_identities.add(model_identity)
        runtime_versions.add(runtime_version)
    if not model_identities:
        raise ValueError("confirmation lane has no identity-bearing responses")
    return model_identities, runtime_versions


def _identity(
    treatment_id: str,
    *,
    artifact_sha256: str,
    runtime_sha256: str,
    workload_sha256: str,
    environment_sha256: str,
    base_controls: Mapping[str, Any],
    enabled: bool,
) -> TreatmentIdentity:
    return TreatmentIdentity(
        treatment_id=treatment_id,
        artifact_sha256=artifact_sha256,
        runtime_sha256=runtime_sha256,
        workload_sha256=workload_sha256,
        environment_sha256=environment_sha256,
        controls=MappingProxyType({**base_controls, "kleidiai.enabled": enabled}),
    )


def derive_minimum_capacity_audit(
    archive_path: Path,
    *,
    expected_sha256: str,
    contract: Contract,
    preregistration: Path,
    analysis_lock: Path,
    protocol_lock: Path,
    workload_manifest: Path,
    workload: Path,
    quality_dataset: Path,
    raw_quality_results: Mapping[str, QualityResult],
    raw_quality_output_count: int,
    performix_profile: Mapping[str, Any],
    on_stage: Callable[[str, dict[str, Any]], None] | None = None,
) -> ConfirmedCapacityAudit:
    """Rebuild the one-sided capacity decision without selecting a new boundary."""

    observed_sha256 = _sha256(archive_path)
    if observed_sha256 != expected_sha256:
        raise ValueError("confirmation archive digest does not match its release lock")
    if set(raw_quality_results) != {"kleidiai-disabled", "kleidiai-enabled"}:
        raise ValueError("raw quality verification must contain both treatments")
    preregistered = json.loads(preregistration.read_text(encoding="utf-8"))
    expected_experiment_id = preregistered.get("experiment_id")
    if not isinstance(expected_experiment_id, str) or not expected_experiment_id:
        raise ValueError("confirmation preregistration has no experiment identity")
    analysis = json.loads(analysis_lock.read_text(encoding="utf-8"))
    if analysis != {
        "schema_version": "1.0.0",
        "experiment_id": expected_experiment_id,
        "latency_origin": "scheduled_ns",
        "latency_end": "finished_ns",
        "completion_deadline": "scheduled_window_plus_p95_slo",
        "collector_summary_authoritative": False,
        "required_response_identity": [
            "model_identity", "source_artifact_sha256", "runtime",
            "runtime_version", "threads", "architecture", "cpu_affinity",
            "optimization_control",
        ],
        "failure_rule": (
            "Any missing runtime identity, dispatch delay hidden from latency, or "
            "completion after the measurement window plus the p95 SLO fails that "
            "request. The release decision is re-derived from raw rows rather than "
            "the collector summary."
        ),
    }:
        raise ValueError("confirmation analysis lock is invalid")
    manifest = json.loads(workload_manifest.read_text(encoding="utf-8"))
    if set(manifest) != {
        "schema_version", "capacity_workload_sha256", "quality_workload_sha256"
    } or manifest.get("schema_version") != "1.0.0":
        raise ValueError("confirmation workload manifest is invalid")
    if (
        manifest["capacity_workload_sha256"] != _sha256(workload)
        or manifest["quality_workload_sha256"] != _sha256(quality_dataset)
    ):
        raise ValueError("confirmation workload files differ from the frozen manifest")
    source_ids = tuple(item.request_id for item in load_requests_jsonl(workload))
    with tarfile.open(archive_path, "r:gz") as archive:
        checked = _verify_internal_checksums(archive)
        experiment = _json(archive, "evidence/experiment.json")
        protocol = _json(archive, "evidence/protocol.json")
        if experiment != preregistered:
            raise ValueError("confirmation experiment differs from its committed preregistration")
        if protocol != json.loads(protocol_lock.read_text(encoding="utf-8")):
            raise ValueError("confirmation protocol differs from its committed lock")
        summary = _json(archive, "evidence/capacity/experiment/summary.json")
        confirmations = _json(
            archive, "evidence/capacity/experiment/confirmations.json"
        )
        matched_control, threads = _verify_matched_control(archive)
        identities = _json(archive, "evidence/capacity/artifact-identities.json")
        runtime_bytes = _text(archive, "evidence/runtime-lock.json").encode("utf-8")
        environment_bytes = _text(archive, "evidence/lscpu.txt").encode("utf-8")
        disabled_perf = parse_perf_attribution(
            _text(archive, "evidence/perf-disabled.txt"), r"^kai_run_matmul"
        )
        enabled_perf = parse_perf_attribution(
            _text(archive, "evidence/perf-enabled.txt"), r"^kai_run_matmul"
        )
        if on_stage is not None:
            on_stage("archive", {
                "checksummed_files": checked,
                "matched_control": matched_control,
                "experiment_id": expected_experiment_id,
            })

        quality_results = {
            lane: quality_from_dict(_json(
                archive,
                f"evidence/capacity/experiment/quality/{lane}.json",
            ))
            for lane in ("kleidiai-disabled", "kleidiai-enabled")
        }
        for lane, raw_result in raw_quality_results.items():
            if quality_to_dict(quality_results[lane]) != quality_to_dict(raw_result):
                raise ValueError("confirmation quality summary differs from raw outputs")
        quality = compare_quality(
            quality_results["kleidiai-disabled"],
            quality_results["kleidiai-enabled"],
        )
        if asdict(quality) != _json(
            archive, "evidence/capacity/experiment/quality/comparison.json"
        ):
            raise ValueError("confirmation quality comparison is inconsistent")

        required = int(protocol["confirmations"])
        if not isinstance(confirmations, list) or len(confirmations) != required * 2:
            raise ValueError("confirmation set does not match the frozen repetition count")
        policy = SloPolicy(
            float(protocol["p95_slo_ms"]),
            float(protocol["max_error_rate"]),
            float(protocol["minimum_delivery_ratio"]),
        )
        raw_count = 0
        file_count = 0
        rederived: list[dict[str, Any]] = []
        model_identities: set[str] = set()
        runtime_versions: set[str] = set()
        frozen_rates = {
            "kleidiai-disabled": float(protocol["baseline_failing_rps"]),
            "kleidiai-enabled": float(protocol["treatment_passing_rps"]),
        }
        for stored in confirmations:
            treatment_id = str(stored["treatment_id"])
            repetition = int(stored["repetition"])
            if treatment_id not in {"kleidiai-disabled", "kleidiai-enabled"}:
                raise ValueError("confirmation contains an unknown treatment")
            name = (
                "evidence/capacity/experiment/confirmations/"
                f"confirm-{repetition}-{treatment_id}.jsonl"
            )
            samples = _parse_samples(
                _text(archive, name),
                treatment_id=treatment_id,
                repetition=repetition,
                source_ids=source_ids,
            )
            requested_rps = float(stored["requested_rps"])
            if not math.isclose(
                requested_rps, frozen_rates[treatment_id], rel_tol=0.0, abs_tol=1e-12
            ):
                raise ValueError(
                    "confirmation request rate differs from its preregistered lane rate"
                )
            duration = float(protocol["confirmation_seconds"])
            if len(samples) != round(requested_rps * duration):
                raise ValueError("confirmation request count differs from frozen cadence")
            interval_ns = int(1_000_000_000 / (len(samples) / duration))
            expected_schedule = [
                samples[0].scheduled_ns + index * interval_ns
                for index in range(len(samples))
            ]
            if [sample.scheduled_ns for sample in samples] != expected_schedule:
                raise ValueError("confirmation cadence differs from its requested rate")
            if samples[-1].scheduled_ns - samples[0].scheduled_ns < duration * 0.98e9:
                raise ValueError("confirmation request window is too short")
            observed_models, observed_runtimes = _verify_response_identities(
                samples,
                treatment_id=treatment_id,
                source_artifact_sha256=str(identities["source"]["sha256"]),
                threads=threads,
            )
            model_identities.update(observed_models)
            runtime_versions.update(observed_runtimes)
            end_to_end, maximum_dispatch_ms = _end_to_end_samples(
                samples,
                duration_seconds=duration,
                slo_ms=policy.p95_latency_ms,
            )
            derived_summary = summary_to_dict(summarize_samples(end_to_end, duration))
            observed_pass = bool(
                derived_summary["p95_ms"] is not None
                and derived_summary["p95_ms"] <= policy.p95_latency_ms
                and derived_summary["error_rate"] <= policy.max_error_rate
                and derived_summary["accepted_rps"]
                >= (len(samples) / duration) * policy.minimum_delivery_ratio
            )
            expected_pass = treatment_id == "kleidiai-enabled"
            derived = {
                "repetition": repetition,
                "treatment_id": treatment_id,
                "requested_rps": requested_rps,
                "offered_rps": len(samples) / duration,
                "expected_pass": expected_pass,
                "observed_pass": observed_pass,
                "matched_expectation": observed_pass is expected_pass,
                "summary": derived_summary,
                "maximum_dispatch_ms": maximum_dispatch_ms,
            }
            stored_identity = {
                key: stored[key]
                for key in (
                    "repetition", "treatment_id", "requested_rps", "offered_rps",
                    "expected_pass",
                )
            }
            if stored_identity != {
                key: derived[key]
                for key in stored_identity
            }:
                raise ValueError("raw confirmation rows disagree with stored window identity")
            rederived.append(derived)
            raw_count += len(samples)
            file_count += 1
        if len(model_identities) != 1 or len(runtime_versions) != 1:
            raise ValueError("confirmation lanes did not use one matched model and runtime")

    if on_stage is not None:
        on_stage("requests", {
            "raw_request_outcomes": raw_count,
            "confirmation_files": file_count,
        })
    experiment_id = str(experiment.get("experiment_id"))
    if (
        experiment_id != expected_experiment_id
        or protocol.get("experiment_id") != experiment_id
        or summary.get("experiment_id") != experiment_id
    ):
        raise ValueError("confirmation experiment identities do not match")
    acceptance = experiment["acceptance"]
    baseline_rate = float(protocol["baseline_failing_rps"])
    treatment_rate = float(protocol["treatment_passing_rps"])
    if (
        baseline_rate != float(acceptance["control_rate_rps"])
        or treatment_rate != float(acceptance["treatment_rate_rps"])
        or float(protocol["minimum_capacity_ratio"])
        != float(acceptance["minimum_capacity_ratio"])
    ):
        raise ValueError("confirmation rates differ from preregistration")
    baseline_rows = [row for row in rederived if row["treatment_id"] == "kleidiai-disabled"]
    treatment_rows = [row for row in rederived if row["treatment_id"] == "kleidiai-enabled"]
    repetitions = set(range(1, int(protocol["confirmations"]) + 1))
    if (
        {row["repetition"] for row in baseline_rows} != repetitions
        or {row["repetition"] for row in treatment_rows} != repetitions
    ):
        raise ValueError("confirmation repetitions are incomplete")
    baseline_failures = sum(not row["observed_pass"] for row in baseline_rows)
    treatment_passes = sum(row["observed_pass"] for row in treatment_rows)
    ratio = treatment_rate / baseline_rate
    quality_passed = bool(
        quality.accuracy_delta_pp >= -float(protocol["maximum_quality_loss_pp"])
        and quality.macro_f1_delta_pp >= -float(protocol["maximum_quality_loss_pp"])
        and min(result.schema_valid_rate for result in quality_results.values())
        >= float(protocol["minimum_schema_valid_rate"])
    )
    passed = bool(
        matched_control
        and baseline_failures == len(baseline_rows)
        and treatment_passes == len(treatment_rows)
        and quality_passed
        and ratio >= float(protocol["minimum_capacity_ratio"])
    )
    if (
        int(summary["raw_request_count"]) != raw_count
        or not math.isclose(float(summary["minimum_capacity_ratio"]), ratio)
    ):
        raise ValueError("confirmation summary disagrees with rederived evidence")

    enabled_profile = performix_profile["enabled"]
    disabled_profile = performix_profile["disabled"]
    if performix_profile.get("experiment_id") != "EXP-2026-013":
        raise ValueError("release requires the confirmatory Performix experiment")
    artifact_sha256 = str(identities["source"]["sha256"])
    runtime_sha256 = hashlib.sha256(runtime_bytes).hexdigest()
    workload_sha256 = _sha256(workload)
    environment_sha256 = hashlib.sha256(environment_bytes).hexdigest()
    base_controls = {
        "threads": threads,
        "instance": "c8g.4xlarge",
        "slo_ms": int(float(protocol["p95_slo_ms"])),
        "matched_overlay": matched_control,
    }
    baseline_identity = _identity(
        "kleidiai-disabled",
        artifact_sha256=artifact_sha256,
        runtime_sha256=runtime_sha256,
        workload_sha256=workload_sha256,
        environment_sha256=environment_sha256,
        base_controls=base_controls,
        enabled=False,
    )
    treatment_identity = _identity(
        "kleidiai-enabled",
        artifact_sha256=artifact_sha256,
        runtime_sha256=runtime_sha256,
        workload_sha256=workload_sha256,
        environment_sha256=environment_sha256,
        base_controls=base_controls,
        enabled=True,
    )
    comparison_id = f"{experiment_id.lower()}-confirmed"
    metrics = {
        "accuracy_delta_pp": quality.accuracy_delta_pp,
        "macro_f1_delta_pp": quality.macro_f1_delta_pp,
        "schema_valid_rate": quality.schema_valid_rate,
        "minimum_capacity_ratio": ratio,
        "raw_confirmation_files": float(file_count),
        "raw_confirmation_samples": float(raw_count),
        "raw_quality_outputs": float(raw_quality_output_count),
        "performix_disabled_kai_share": float(disabled_profile["kai_sample_share"]),
        "performix_enabled_kai_share": float(enabled_profile["kai_sample_share"]),
        "performix_minimum_profile_samples": float(min(
            disabled_profile["total_function_samples"],
            enabled_profile["total_function_samples"],
        )),
    }
    comparison = Comparison(
        comparison_id=comparison_id,
        causal_scope=CausalScope.ARM_ACCELERATION,
        baseline=baseline_identity,
        treatment=treatment_identity,
        metrics=MappingProxyType(metrics),
        evidence_kinds=frozenset({
            "quality_rows", "raw_model_outputs", "artifact_hashes",
            "performix_code_hotspots", "request_samples", "boundary_confirmations",
            "runtime_lock", "workload_manifest", "environment_identity",
        }),
        arm_path_baseline_observed=disabled_profile["kai_function_samples"] > 0,
        arm_path_treatment_observed=enabled_profile["kai_function_samples"] > 0,
    )
    comparison_ids = {claim.comparison_id for claim in contract.claims}
    if comparison_ids != {comparison_id}:
        raise ValueError("confirmation contract must bind only the confirmatory comparison")
    declared = {row.treatment_id: row for row in contract.treatments}
    expected_environments = {
        "kleidiai-disabled": {
            "mlas.disable_kleidiai": "1", "intra_op_num_threads": str(threads),
        },
        "kleidiai-enabled": {
            "mlas.disable_kleidiai": "0", "intra_op_num_threads": str(threads),
        },
    }
    for treatment_id, environment in expected_environments.items():
        if treatment_id not in declared or dict(declared[treatment_id].environment) != environment:
            raise ValueError("confirmation contract does not declare the matched control")
    validate_comparison_identities(contract, (comparison,))
    decision = evaluate_claims(contract.claims, (comparison,))
    if decision.passed is not passed:
        raise ValueError("confirmation contract and preregistered experiment disagree")
    return ConfirmedCapacityAudit(
        experiment_id=experiment_id,
        archive_sha256=observed_sha256,
        passed=passed,
        baseline_failing_rps=baseline_rate,
        treatment_passing_rps=treatment_rate,
        minimum_capacity_ratio=ratio,
        confirmation_seconds=int(float(protocol["confirmation_seconds"])),
        confirmations_per_treatment=int(protocol["confirmations"]),
        baseline_failures=baseline_failures,
        treatment_passes=treatment_passes,
        baseline_p95_ms=tuple(float(row["summary"]["p95_ms"]) for row in baseline_rows),
        treatment_p95_ms=tuple(float(row["summary"]["p95_ms"]) for row in treatment_rows),
        baseline_max_dispatch_ms=tuple(
            float(row["maximum_dispatch_ms"]) for row in baseline_rows
        ),
        treatment_max_dispatch_ms=tuple(
            float(row["maximum_dispatch_ms"]) for row in treatment_rows
        ),
        raw_confirmation_files=file_count,
        raw_confirmation_samples=raw_count,
        raw_quality_outputs=raw_quality_output_count,
        accuracy_delta_pp=quality.accuracy_delta_pp,
        macro_f1_delta_pp=quality.macro_f1_delta_pp,
        schema_valid_rate=quality.schema_valid_rate,
        matched_control_verified=matched_control,
        internal_checksummed_files=checked,
        disabled_kai_cycle_share=disabled_perf.maximum_children_share,
        enabled_kai_cycle_share=enabled_perf.maximum_children_share,
        lost_perf_samples=disabled_perf.lost_samples + enabled_perf.lost_samples,
        comparison=comparison,
        decision=decision,
    )
