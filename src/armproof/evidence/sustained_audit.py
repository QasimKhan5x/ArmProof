"""Derive conservative release facts from a checksum-bound sustained audit."""

from __future__ import annotations

import hashlib
import json
import tarfile
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from armproof.contracts import Contract, validate_comparison_identities
from armproof.domain import CausalScope, Comparison, Decision, TreatmentIdentity
from armproof.policy import evaluate_claims
from armproof.profiling import parse_perf_attribution
from armproof.quality import compare_quality, quality_from_dict
from armproof.workload.io import summary_to_dict
from armproof.workload.load import RequestSample, summarize_samples


@dataclass(frozen=True)
class SustainedAudit:
    experiment_id: str
    archive_sha256: str
    original_gate_passed: bool
    corrected_claim_passed: bool
    baseline_pass_rps: float
    baseline_fail_rps: float
    treatment_pass_rps: float
    treatment_fail_rps: float
    tested_pass_point_ratio: float
    minimum_capacity_ratio: float
    confirmations: int
    confirmation_seconds: int
    baseline_passes: int
    baseline_failures_at_fail_probe: int
    treatment_passes: int
    treatment_failures_at_fail_probe: int
    baseline_pass_p95_ms: tuple[float, ...]
    treatment_pass_p95_ms: tuple[float, ...]
    treatment_fail_probe_p95_ms: tuple[float, ...]
    quality_passed: bool
    accuracy_delta_pp: float
    macro_f1_delta_pp: float
    schema_valid_rate: float
    disabled_kai_cycle_share: float
    enabled_kai_cycle_share: float
    lost_perf_samples: int
    raw_samples_rederived: bool
    raw_confirmation_files: int
    raw_confirmation_samples: int
    matched_control_verified: bool
    only_changed_control: str
    internal_checksums_verified: bool
    internal_checksummed_files: int
    comparison: Comparison
    decision: Decision


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _local_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_workloads(manifest_path: Path) -> tuple[dict[str, str], tuple[str, ...]]:
    manifest = _local_json(manifest_path)
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("workload manifest is missing output identities")
    verified: dict[str, Path] = {}
    for name in ("quality.jsonl", "traffic-mixed.jsonl"):
        record = outputs.get(name)
        path = manifest_path.parent / name
        if not isinstance(record, dict) or _sha256(path) != record.get("sha256"):
            raise ValueError(f"frozen workload digest does not match: {name}")
        if len(path.read_text(encoding="utf-8").splitlines()) != int(record["rows"]):
            raise ValueError(f"frozen workload row count does not match: {name}")
        verified[name] = path
    quality = {
        row["request_id"]: row["expected_intent"]
        for row in (
            json.loads(line)
            for line in verified["quality.jsonl"].read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    traffic = tuple(
        row["request_id"]
        for row in (
            json.loads(line)
            for line in verified["traffic-mixed.jsonl"].read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    )
    if len(quality) != int(outputs["quality.jsonl"]["rows"]) or len(set(traffic)) != len(traffic):
        raise ValueError("frozen workloads contain duplicate request IDs")
    return quality, traffic


def _text(archive: tarfile.TarFile, name: str) -> str:
    member = archive.getmember(name)
    stream = archive.extractfile(member)
    if stream is None:
        raise ValueError(f"sustained audit member is not a file: {name}")
    return stream.read().decode("utf-8")


def _json(archive: tarfile.TarFile, name: str) -> Any:
    return json.loads(_text(archive, name))


def _verify_internal_checksums(archive: tarfile.TarFile) -> int:
    prefix = "/opt/armproof/evidence/"
    checked: set[str] = set()
    for line in _text(archive, "evidence/SHA256SUMS").splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64 or not parts[1].startswith(prefix):
            raise ValueError("sustained audit contains an invalid checksum entry")
        expected, original_path = parts
        relative = original_path.removeprefix(prefix)
        if not relative or relative in checked or ".." in Path(relative).parts:
            raise ValueError("sustained audit contains an unsafe checksum path")
        member = archive.getmember(f"evidence/{relative}")
        stream = archive.extractfile(member)
        if not member.isfile() or stream is None:
            raise ValueError("sustained audit checksum entry is not a regular file")
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ValueError(f"sustained audit checksum mismatch: {relative}")
        checked.add(relative)
    if not checked:
        raise ValueError("sustained audit checksum ledger is empty")
    return len(checked)


def _constant_rate(rows: list[dict[str, Any]], boundary: str) -> float:
    rates = {float(row[boundary]["requested_rps"]) for row in rows}
    if len(rates) != 1:
        raise ValueError(f"sustained audit has inconsistent {boundary} rates")
    return rates.pop()


def _rederive_confirmations(
    archive: tarfile.TarFile,
    confirmations: dict[str, Any],
    protocol: dict[str, Any],
    traffic_ids: tuple[str, ...],
) -> tuple[dict[str, Any], int, int]:
    duration = float(protocol["confirmation_seconds"])
    p95_limit = float(protocol["mixes"][0]["p95_slo_ms"])
    max_error_rate = float(protocol["max_error_rate"])
    minimum_delivery_ratio = float(protocol["minimum_delivery_ratio"])
    minimum_samples = int(protocol["minimum_confirmation_requests"])
    rederived: dict[str, Any] = {"mixed": {}}
    file_count = 0
    sample_count = 0
    observed_request_ids: set[str] = set()
    for treatment in ("kleidiai-disabled", "kleidiai-enabled"):
        output_rows = []
        stored_rows = confirmations["mixed"][treatment]
        repetitions = {int(row["repetition"]) for row in stored_rows}
        if repetitions != set(range(1, int(protocol["confirmations"]) + 1)):
            raise ValueError(f"sustained audit has invalid repetitions for {treatment}")
        for stored_row in stored_rows:
            repetition = int(stored_row["repetition"])
            output_row: dict[str, Any] = {"repetition": repetition}
            for boundary in ("pass", "fail"):
                requested_rps = float(stored_row[boundary]["requested_rps"])
                name = (
                    "evidence/capacity/experiment/capacity/mixed/"
                    f"{treatment}/confirmations/rep-{repetition}-{boundary}.jsonl"
                )
                raw_rows = [
                    json.loads(line)
                    for line in _text(archive, name).splitlines()
                    if line.strip()
                ]
                for index, row in enumerate(raw_rows):
                    expected_source_id = traffic_ids[index % len(traffic_ids)]
                    expected_request_id = (
                        f"confirm-{repetition}-mixed-{treatment}-{boundary}-"
                        f"{index:06d}-{expected_source_id}"
                    )
                    response = row.get("response")
                    if row.get("request_id") != expected_request_id:
                        raise ValueError(f"sustained request sequence disagrees with {name}")
                    if expected_request_id in observed_request_ids:
                        raise ValueError("sustained audit contains duplicate request IDs")
                    if isinstance(response, dict):
                        if response.get("backend") != treatment:
                            raise ValueError(f"sustained response backend disagrees with {name}")
                        if response.get("request_id") != expected_source_id:
                            raise ValueError(f"sustained source request ID disagrees with {name}")
                    elif row.get("status_code") == 200 or not row.get("error"):
                        raise ValueError(f"sustained response attribution is missing in {name}")
                    if not (
                        int(row["scheduled_ns"]) <= int(row["started_ns"])
                        <= int(row["finished_ns"])
                    ):
                        raise ValueError(f"sustained request timestamps are invalid in {name}")
                    observed_request_ids.add(expected_request_id)
                scheduled = [int(row["scheduled_ns"]) for row in raw_rows]
                if scheduled != sorted(set(scheduled)):
                    raise ValueError(f"sustained request schedule is not strictly ordered in {name}")
                interval_ns = int(1_000_000_000 / requested_rps)
                expected_schedule = [scheduled[0] + index * interval_ns for index in range(len(scheduled))]
                if scheduled != expected_schedule:
                    raise ValueError(f"sustained request cadence disagrees with {name}")
                if scheduled[-1] - scheduled[0] < duration * 0.98 * 1_000_000_000:
                    raise ValueError(f"sustained request window is too short in {name}")
                if max(int(row["started_ns"]) - int(row["scheduled_ns"]) for row in raw_rows) > 1_000_000_000:
                    raise ValueError(f"sustained request dispatch delay is excessive in {name}")
                samples = [
                    RequestSample(
                        request_id=str(row["request_id"]),
                        scheduled_ns=int(row["scheduled_ns"]),
                        started_ns=int(row["started_ns"]),
                        finished_ns=int(row["finished_ns"]),
                        status_code=row["status_code"],
                        error=row["error"],
                        response=row["response"],
                    )
                    for row in raw_rows
                ]
                summary = summary_to_dict(summarize_samples(samples, duration))
                expected_samples = round(requested_rps * duration)
                offered_rps = len(samples) / duration
                passed = bool(
                    len(samples) == expected_samples
                    and summary["total"] >= minimum_samples
                    and summary["p95_ms"] is not None
                    and summary["p95_ms"] <= p95_limit
                    and summary["error_rate"] <= max_error_rate
                    and summary["accepted_rps"]
                    >= requested_rps * minimum_delivery_ratio
                )
                if summary != stored_row[boundary]["summary"]:
                    raise ValueError(f"raw sustained samples disagree with {name} summary")
                if offered_rps != float(stored_row[boundary]["offered_rps"]):
                    raise ValueError(f"raw sustained samples disagree with {name} offered rate")
                if passed != bool(stored_row[boundary]["passed"]):
                    raise ValueError(f"raw sustained samples disagree with {name} decision")
                output_row[boundary] = {
                    "requested_rps": requested_rps,
                    "offered_rps": offered_rps,
                    "passed": passed,
                    "summary": summary,
                }
                file_count += 1
                sample_count += len(samples)
            output_rows.append(output_row)
        rederived["mixed"][treatment] = output_rows
    return rederived, file_count, sample_count


def _verify_matched_control(archive: tarfile.TarFile) -> bool:
    prefixes = {
        treatment: f"evidence/capacity/variants/{treatment}/"
        for treatment in ("disabled", "enabled")
    }
    variant_members: dict[str, dict[str, tarfile.TarInfo]] = {}
    for treatment, prefix in prefixes.items():
        variant_members[treatment] = {
            member.name.removeprefix(prefix): member
            for member in archive.getmembers()
            if member.name.startswith(prefix)
            and member.name.rstrip("/") != prefix.rstrip("/")
        }
    if set(variant_members["disabled"]) != set(variant_members["enabled"]):
        return False
    for relative_name in set(variant_members["disabled"]) - {"genai_config.json"}:
        disabled_member = variant_members["disabled"][relative_name]
        enabled_member = variant_members["enabled"][relative_name]
        if not (
            disabled_member.issym()
            and enabled_member.issym()
            and disabled_member.linkname == enabled_member.linkname
        ):
            return False
    disabled = _json(
        archive, "evidence/capacity/variants/disabled/genai_config.json"
    )
    enabled = _json(
        archive, "evidence/capacity/variants/enabled/genai_config.json"
    )
    path = ("model", "decoder", "session_options")
    disabled_entries = disabled
    enabled_entries = enabled
    for key in path:
        disabled_entries = disabled_entries[key]
        enabled_entries = enabled_entries[key]
    control = "mlas.disable_kleidiai"
    if disabled_entries.get(control) != "1" or enabled_entries.get(control) != "0":
        return False
    disabled_entries[control] = "0"
    return disabled == enabled


def derive_sustained_audit(
    archive_path: Path,
    *,
    expected_sha256: str,
    contract: Contract,
    workload_manifest: Path,
) -> SustainedAudit:
    """Verify an immutable archive and derive a bounded, non-exact capacity claim."""

    observed_sha256 = _sha256(archive_path)
    if observed_sha256 != expected_sha256:
        raise ValueError("sustained audit archive digest does not match its release lock")

    quality_labels, traffic_ids = _verify_workloads(workload_manifest)
    with tarfile.open(archive_path, "r:gz") as archive:
        internal_check_count = _verify_internal_checksums(archive)
        experiment = _json(archive, "evidence/experiment.json")
        protocol = _json(archive, "evidence/protocol.json")
        summary = _json(archive, "evidence/capacity/experiment/summary.json")
        confirmations = _json(
            archive, "evidence/capacity/experiment/confirmations.json"
        )
        confirmations, raw_file_count, raw_sample_count = _rederive_confirmations(
            archive, confirmations, protocol, traffic_ids
        )
        disabled_perf = parse_perf_attribution(
            _text(archive, "evidence/perf-disabled.txt"), r"^kai_run_matmul"
        )
        enabled_perf = parse_perf_attribution(
            _text(archive, "evidence/perf-enabled.txt"), r"^kai_run_matmul"
        )
        matched_control = _verify_matched_control(archive)
        disabled_config = _json(
            archive, "evidence/capacity/variants/disabled/genai_config.json"
        )
        enabled_config = _json(
            archive, "evidence/capacity/variants/enabled/genai_config.json"
        )
        identities = _json(archive, "evidence/capacity/artifact-identities.json")
        runtime_lock = _json(archive, "evidence/runtime-lock.json")
        runtime_bytes = _text(archive, "evidence/runtime-lock.json").encode("utf-8")
        environment_bytes = archive.extractfile(
            archive.getmember("evidence/lscpu.txt")
        ).read()
        quality_baseline = quality_from_dict(
            _json(
                archive,
                "evidence/capacity/experiment/quality/kleidiai-disabled.json",
            )
        )
        quality_treatment = quality_from_dict(
            _json(
                archive,
                "evidence/capacity/experiment/quality/kleidiai-enabled.json",
            )
        )
        quality_comparison = compare_quality(quality_baseline, quality_treatment)
        for result in (quality_baseline, quality_treatment):
            observed_labels = {
                row.request_id: row.expected_intent for row in result.rows
            }
            if observed_labels != quality_labels:
                raise ValueError("sustained quality rows do not match the frozen workload")
        recorded_quality_comparison = _json(
            archive, "evidence/capacity/experiment/quality/comparison.json"
        )
        if asdict(quality_comparison) != recorded_quality_comparison:
            raise ValueError("sustained quality rows disagree with comparison summary")

    experiment_id = str(experiment.get("experiment_id"))
    if (
        experiment_id != "EXP-2026-009"
        or protocol.get("experiment_id") != experiment_id
        or summary.get("experiment_id") != experiment_id
    ):
        raise ValueError("sustained audit experiment identities do not match")
    rows = confirmations.get("mixed")
    if not isinstance(rows, dict):
        raise ValueError("sustained audit is missing the mixed traffic confirmation set")
    baseline = rows.get("kleidiai-disabled")
    treatment = rows.get("kleidiai-enabled")
    required = int(protocol["confirmations"])
    if not isinstance(baseline, list) or not isinstance(treatment, list):
        raise ValueError("sustained audit is missing matched treatment confirmations")
    if len(baseline) != required or len(treatment) != required:
        raise ValueError("sustained audit confirmation count does not match its protocol")
    if (
        int(experiment["acceptance"]["confirmations"]) != required
        or float(experiment["acceptance"]["confirmation_seconds"])
        != float(protocol["confirmation_seconds"])
        or int(experiment["acceptance"]["minimum_requests_per_confirmation"])
        != int(protocol["minimum_confirmation_requests"])
    ):
        raise ValueError("sustained protocol does not match preregistered duration or counts")

    fixed_boundaries = {
        row["treatment_id"]: (float(row["passing_rps"]), float(row["failing_rps"]))
        for row in protocol.get("fixed_boundaries", [])
        if row.get("mix_id") == "mixed"
    }
    if set(fixed_boundaries) != {"kleidiai-disabled", "kleidiai-enabled"}:
        raise ValueError("sustained protocol does not contain the frozen mixed boundaries")

    baseline_pass_rps = _constant_rate(baseline, "pass")
    baseline_fail_rps = _constant_rate(baseline, "fail")
    treatment_pass_rps = _constant_rate(treatment, "pass")
    treatment_fail_rps = _constant_rate(treatment, "fail")
    observed_boundaries = {
        "kleidiai-disabled": (baseline_pass_rps, baseline_fail_rps),
        "kleidiai-enabled": (treatment_pass_rps, treatment_fail_rps),
    }
    acceptance_boundaries = {
        "kleidiai-disabled": (
            float(experiment["acceptance"]["disabled_pass_rps"]),
            float(experiment["acceptance"]["disabled_fail_rps"]),
        ),
        "kleidiai-enabled": (
            float(experiment["acceptance"]["enabled_pass_rps"]),
            float(experiment["acceptance"]["enabled_fail_rps"]),
        ),
    }
    if observed_boundaries != fixed_boundaries or observed_boundaries != acceptance_boundaries:
        raise ValueError("sustained boundaries do not match preregistration and protocol")
    if not (
        baseline_pass_rps < baseline_fail_rps
        and treatment_pass_rps < treatment_fail_rps
    ):
        raise ValueError("sustained audit pass/fail boundaries are not ordered")
    baseline_passes = sum(bool(row["pass"]["passed"]) for row in baseline)
    baseline_failures = sum(not bool(row["fail"]["passed"]) for row in baseline)
    treatment_passes = sum(bool(row["pass"]["passed"]) for row in treatment)
    treatment_failures = sum(not bool(row["fail"]["passed"]) for row in treatment)
    quality = asdict(quality_comparison)
    if quality != summary["quality_comparison"]:
        raise ValueError("sustained quality rows disagree with experiment summary")
    quality_passed = bool(
        quality_comparison.accuracy_delta_pp
        >= -float(experiment["acceptance"]["maximum_quality_loss_pp"])
        and quality_comparison.macro_f1_delta_pp
        >= -float(experiment["acceptance"]["maximum_quality_loss_pp"])
        and quality_baseline.schema_valid_rate >= float(protocol["minimum_schema_valid_rate"])
        and quality_treatment.schema_valid_rate >= float(protocol["minimum_schema_valid_rate"])
    )
    if quality_passed != bool(summary["quality_passed"]):
        raise ValueError("sustained quality rows disagree with quality decision")
    tested_ratio = treatment_pass_rps / baseline_pass_rps
    minimum_ratio = treatment_pass_rps / baseline_fail_rps
    lost_samples = disabled_perf.lost_samples + enabled_perf.lost_samples
    if (
        disabled_perf.event != "cycles:P"
        or enabled_perf.event != "cycles:P"
        or min(disabled_perf.samples, enabled_perf.samples) < 10_000
    ):
        raise ValueError("sustained perf evidence lacks a sampled cycles event")
    original_gate_passed = bool(
        quality_passed
        and baseline_passes == required
        and baseline_failures == required
        and treatment_passes == required
        and treatment_failures == required
    )
    if original_gate_passed != bool(summary["passed"]):
        raise ValueError("raw sustained samples disagree with original gate decision")
    if not (
        baseline_passes == required
        and baseline_failures == required
        and treatment_passes == required
    ):
        minimum_ratio = 0.0
    artifact_sha256 = str(identities["source"]["sha256"])
    runtime_sha256 = _sha256_bytes(runtime_bytes)
    workload_sha256 = _sha256(workload_manifest)
    environment_sha256 = _sha256_bytes(environment_bytes)
    disabled_session = disabled_config["model"]["decoder"]["session_options"]
    enabled_session = enabled_config["model"]["decoder"]["session_options"]
    threads = int(disabled_session["intra_op_num_threads"])
    if int(enabled_session["intra_op_num_threads"]) != threads:
        raise ValueError("sustained treatment thread counts do not match")
    if runtime_lock.get("hardware") != "AWS Graviton4 / c8g.4xlarge / 16 cores":
        raise ValueError("sustained runtime lock does not identify the measured machine")
    base_controls = {
        "threads": threads,
        "instance": "c8g.4xlarge",
        "slo_ms": int(float(protocol["mixes"][0]["p95_slo_ms"])),
        "matched_overlay": True,
    }
    declared = {row.treatment_id: row for row in contract.treatments}
    expected_commands = {
        "kleidiai-disabled": (
            "python", "-m", "armproof.reference.phi4", "--backend", "ort-int4",
            "--model", "/opt/armproof/evidence/capacity/variants/disabled",
            "--label", "kleidiai-disabled", "--port", "8000", "--threads",
            str(threads), "--max-inflight", "1",
        ),
        "kleidiai-enabled": (
            "python", "-m", "armproof.reference.phi4", "--backend", "ort-int4",
            "--model", "/opt/armproof/evidence/capacity/variants/enabled",
            "--label", "kleidiai-enabled", "--port", "8001", "--threads",
            str(threads), "--max-inflight", "1",
        ),
    }
    expected_environments = {
        "kleidiai-disabled": {
            "mlas.disable_kleidiai": str(disabled_session["mlas.disable_kleidiai"]),
            "intra_op_num_threads": str(threads),
        },
        "kleidiai-enabled": {
            "mlas.disable_kleidiai": str(enabled_session["mlas.disable_kleidiai"]),
            "intra_op_num_threads": str(threads),
        },
    }
    for treatment_id, expected_environment in expected_environments.items():
        declaration = declared.get(treatment_id)
        if declaration is None or declaration.command != expected_commands[treatment_id]:
            raise ValueError(f"sustained contract command is unsupported: {treatment_id}")
        if dict(declaration.environment) != expected_environment:
            raise ValueError(f"sustained contract environment does not match: {treatment_id}")
    baseline_identity = TreatmentIdentity(
        treatment_id="kleidiai-disabled",
        artifact_sha256=artifact_sha256,
        runtime_sha256=runtime_sha256,
        workload_sha256=workload_sha256,
        environment_sha256=environment_sha256,
        controls=MappingProxyType(
            {**base_controls, "kleidiai.enabled": False}
        ),
    )
    treatment_identity = TreatmentIdentity(
        treatment_id="kleidiai-enabled",
        artifact_sha256=artifact_sha256,
        runtime_sha256=runtime_sha256,
        workload_sha256=workload_sha256,
        environment_sha256=environment_sha256,
        controls=MappingProxyType(
            {
                **base_controls,
                "matched_overlay": matched_control,
                "kleidiai.enabled": True,
            }
        ),
    )
    comparison = Comparison(
        comparison_id="exp-2026-009-sustained",
        causal_scope=CausalScope.ARM_ACCELERATION,
        baseline=baseline_identity,
        treatment=treatment_identity,
        metrics=MappingProxyType(
            {
                "accuracy_delta_pp": quality_comparison.accuracy_delta_pp,
                "macro_f1_delta_pp": quality_comparison.macro_f1_delta_pp,
                "schema_valid_rate": quality_comparison.schema_valid_rate,
                "minimum_capacity_ratio": minimum_ratio,
                "raw_confirmation_files": float(raw_file_count),
                "raw_confirmation_samples": float(raw_sample_count),
                "enabled_kai_callchains_observed": float(
                    enabled_perf.maximum_children_share > 0
                ),
                "enabled_kai_cycle_callchain_share": enabled_perf.maximum_children_share,
                "lost_perf_samples": float(lost_samples),
            }
        ),
        evidence_kinds=frozenset(
            {
                "quality_rows",
                "artifact_hashes",
                "arm_callchains",
                "request_samples",
                "boundary_confirmations",
                "runtime_lock",
                "workload_manifest",
                "environment_identity",
            }
        ),
        arm_path_baseline_observed=disabled_perf.maximum_children_share > 0,
        arm_path_treatment_observed=enabled_perf.maximum_children_share > 0,
    )
    validate_comparison_identities(contract, (comparison,))
    decision = evaluate_claims(contract.claims, (comparison,))
    corrected_claim_passed = decision.passed

    return SustainedAudit(
        experiment_id=experiment_id,
        archive_sha256=observed_sha256,
        original_gate_passed=original_gate_passed,
        corrected_claim_passed=corrected_claim_passed,
        baseline_pass_rps=baseline_pass_rps,
        baseline_fail_rps=baseline_fail_rps,
        treatment_pass_rps=treatment_pass_rps,
        treatment_fail_rps=treatment_fail_rps,
        tested_pass_point_ratio=tested_ratio,
        minimum_capacity_ratio=minimum_ratio,
        confirmations=required,
        confirmation_seconds=int(protocol["confirmation_seconds"]),
        baseline_passes=baseline_passes,
        baseline_failures_at_fail_probe=baseline_failures,
        treatment_passes=treatment_passes,
        treatment_failures_at_fail_probe=treatment_failures,
        baseline_pass_p95_ms=tuple(
            float(row["pass"]["summary"]["p95_ms"]) for row in baseline
        ),
        treatment_pass_p95_ms=tuple(
            float(row["pass"]["summary"]["p95_ms"]) for row in treatment
        ),
        treatment_fail_probe_p95_ms=tuple(
            float(row["fail"]["summary"]["p95_ms"]) for row in treatment
        ),
        quality_passed=quality_passed,
        accuracy_delta_pp=float(quality["accuracy_delta_pp"]),
        macro_f1_delta_pp=float(quality["macro_f1_delta_pp"]),
        schema_valid_rate=float(quality["schema_valid_rate"]),
        disabled_kai_cycle_share=disabled_perf.maximum_children_share,
        enabled_kai_cycle_share=enabled_perf.maximum_children_share,
        lost_perf_samples=lost_samples,
        raw_samples_rederived=True,
        raw_confirmation_files=raw_file_count,
        raw_confirmation_samples=raw_sample_count,
        matched_control_verified=matched_control,
        only_changed_control="mlas.disable_kleidiai",
        internal_checksums_verified=True,
        internal_checksummed_files=internal_check_count,
        comparison=comparison,
        decision=decision,
    )
