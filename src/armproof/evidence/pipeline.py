"""Derive one ArmProof comparison from checksum-bound raw reference evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from armproof.contracts import Contract, validate_comparison_identities
from armproof.demo.queue_guard import QueueGuard, queue_for_intent
from armproof.domain import CausalScope, Comparison, TreatmentIdentity
from armproof.evidence.checksums import ChecksumResult, verify_checksum_ledger
from armproof.policy.statistics import estimate_ratio
from armproof.quality import compare_quality, load_quality_cases, quality_from_dict
from armproof.workload import RequestSample, SloPolicy, summarize_samples


ADAPTER_ID = "kleidiai-capacity-v1"
TREATMENT_IDS = ("kleidiai-disabled", "kleidiai-enabled")


@dataclass(frozen=True)
class VerifiedEvidence:
    comparison: Comparison
    summary: Mapping[str, Any]
    checksums: ChecksumResult
    reproduction_checksums: ChecksumResult | None
    adapter: str = ADAPTER_ID


def _json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read evidence JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"evidence JSON must be an object: {path}")
    return payload


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _verify_workload_manifest(path: Path) -> dict[str, Any]:
    manifest = _json(path)
    if manifest.get("schema_version") != "1.0.0":
        raise ValueError("workload manifest must use schema 1.0.0")
    generated = path.parent
    source = generated.parent / "source"
    groups = (
        (manifest.get("outputs"), generated),
        (manifest.get("source_hashes"), source),
    )
    for rows, directory in groups:
        if not isinstance(rows, dict) or not rows:
            raise ValueError("workload manifest has incomplete file identities")
        for name, identity in rows.items():
            expected = identity.get("sha256") if isinstance(identity, dict) else identity
            candidate = directory / name
            if not isinstance(expected, str) or _sha256(candidate) != expected:
                raise ValueError(f"workload manifest hash mismatch: {candidate}")
    return manifest


def _samples(path: Path) -> list[RequestSample]:
    rows: list[RequestSample] = []
    seen: set[str] = set()
    required = {
        "request_id", "scheduled_ns", "started_ns", "finished_ns", "latency_ms",
        "status_code", "error", "response",
    }
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid request evidence {path}:{line_number}") from exc
        if not isinstance(payload, dict) or set(payload) != required:
            raise ValueError(f"invalid request evidence fields {path}:{line_number}")
        request_id = payload["request_id"]
        if not isinstance(request_id, str) or not request_id or request_id in seen:
            raise ValueError(f"invalid or duplicate request ID {path}:{line_number}")
        sample = RequestSample(
            request_id=request_id,
            scheduled_ns=payload["scheduled_ns"],
            started_ns=payload["started_ns"],
            finished_ns=payload["finished_ns"],
            status_code=payload["status_code"],
            error=payload["error"],
            response=payload["response"],
        )
        if not isinstance(payload["latency_ms"], (int, float)) or not math.isclose(
            sample.latency_ms, float(payload["latency_ms"]), rel_tol=1e-9, abs_tol=1e-6
        ):
            raise ValueError(f"request latency disagrees with timestamps {path}:{line_number}")
        seen.add(request_id)
        rows.append(sample)
    if not rows:
        raise ValueError(f"request evidence is empty: {path}")
    return rows


def _passes(summary: Any, offered_rps: float, policy: SloPolicy) -> bool:
    return bool(
        summary.p95_ms is not None
        and summary.p95_ms <= policy.p95_latency_ms
        and summary.error_rate <= policy.max_error_rate
        and summary.accepted_rps >= offered_rps * policy.minimum_delivery_ratio
    )


def _derive_capacity(
    evidence_root: Path,
    protocol_payload: Mapping[str, Any],
) -> dict[str, Any]:
    protocol = protocol_payload.get("protocol")
    if not isinstance(protocol, dict):
        raise ValueError("capacity protocol is missing")
    seconds = protocol.get("confirmation_seconds")
    repetitions = protocol.get("confirmations")
    if not isinstance(seconds, (int, float)) or seconds <= 0:
        raise ValueError("confirmation duration is invalid")
    if not isinstance(repetitions, int) or repetitions < 5:
        raise ValueError("at least five raw boundary confirmations are required")
    mixes = protocol.get("mixes")
    if not isinstance(mixes, list) or {row.get("mix_id") for row in mixes if isinstance(row, dict)} != {
        "short", "long", "mixed",
    }:
        raise ValueError("capacity protocol must contain short, long, and mixed traffic")

    result: dict[str, Any] = {}
    experiment = evidence_root / "capacity/experiment"
    for mix in mixes:
        mix_id = mix["mix_id"]
        policy = SloPolicy(
            float(mix["p95_slo_ms"]),
            float(protocol["max_error_rate"]),
            float(protocol["minimum_delivery_ratio"]),
        )
        rates: dict[str, list[float]] = {name: [] for name in TREATMENT_IDS}
        fail_rates: dict[str, list[float]] = {name: [] for name in TREATMENT_IDS}
        for treatment_id in TREATMENT_IDS:
            for repetition in range(1, repetitions + 1):
                directory = experiment / "capacity" / mix_id / treatment_id / "confirmations"
                pass_rows = _samples(directory / f"rep-{repetition}-pass.jsonl")
                fail_rows = _samples(directory / f"rep-{repetition}-fail.jsonl")
                pass_summary = summarize_samples(pass_rows, float(seconds))
                fail_summary = summarize_samples(fail_rows, float(seconds))
                pass_offered = len(pass_rows) / float(seconds)
                fail_offered = len(fail_rows) / float(seconds)
                if not _passes(pass_summary, pass_offered, policy):
                    raise ValueError(
                        f"raw passing boundary failed: {mix_id}/{treatment_id}/rep-{repetition}"
                    )
                if _passes(fail_summary, fail_offered, policy):
                    raise ValueError(
                        f"raw failing boundary passed: {mix_id}/{treatment_id}/rep-{repetition}"
                    )
                if pass_offered >= fail_offered:
                    raise ValueError(f"capacity boundary is not ordered: {mix_id}/{treatment_id}")
                rates[treatment_id].append(pass_summary.accepted_rps)
                fail_rates[treatment_id].append(fail_offered)
        estimate = estimate_ratio(
            rates["kleidiai-enabled"],
            rates["kleidiai-disabled"],
            seed=20260731,
        )
        result[mix_id] = {
            "valid_boundary_confirmations": True,
            "disabled_boundary": [
                estimate.baseline_median,
                min(fail_rates["kleidiai-disabled"]),
            ],
            "enabled_boundary": [
                estimate.treatment_median,
                min(fail_rates["kleidiai-enabled"]),
            ],
            "ratio": asdict(estimate),
        }
    return result


def _operational_queue_accuracy(workload_manifest: Path, quality_rows: Any) -> float:
    source_csv = workload_manifest.parent.parent / "source/test.csv"
    with source_csv.open(encoding="utf-8", newline="") as stream:
        source_rows = list(csv.DictReader(stream))
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in source_rows:
        if set(row) != {"category", "text"}:
            raise ValueError("BANKING77 source rows have unexpected fields")
        grouped[row["category"]].append(row)
    evaluation: list[dict[str, str]] = []
    training: list[dict[str, str]] = []
    for rows in grouped.values():
        evaluation.extend(rows[:10])
        training.extend(rows[10:])
    quality_cases = load_quality_cases(workload_manifest.parent / "quality.jsonl")
    if [case.source_text for case in quality_cases] != [row["text"] for row in evaluation]:
        raise ValueError("operational holdout does not match the frozen quality workload")
    if {row.request_id for row in quality_rows} != {case.request.request_id for case in quality_cases}:
        raise ValueError("quality evidence request IDs do not match the frozen workload")
    guard = QueueGuard(
        (row["text"], queue_for_intent(row["category"])) for row in training
    )
    correct = sum(
        guard.predict(row["text"]).queue == queue_for_intent(row["category"])
        for row in evaluation
    )
    return correct / len(evaluation)


def _identity(
    treatment_id: str,
    experiment: Mapping[str, Any],
    *,
    artifact_sha256: str,
    runtime_sha256: str,
    workload_sha256: str,
    environment_sha256: str,
    instance: str,
) -> TreatmentIdentity:
    rows = experiment.get("treatments")
    if not isinstance(rows, list):
        raise ValueError("experiment treatments are missing")
    row = next((item for item in rows if item.get("id") == treatment_id), None)
    if not isinstance(row, dict) or not isinstance(row.get("environment_overrides"), dict):
        raise ValueError(f"experiment treatment is missing: {treatment_id}")
    overrides = row["environment_overrides"]
    disabled = str(overrides.get("mlas.disable_kleidiai"))
    threads = overrides.get("intra_op_num_threads")
    if disabled not in {"0", "1"} or not isinstance(threads, int) or threads < 1:
        raise ValueError(f"experiment controls are invalid: {treatment_id}")
    return TreatmentIdentity(
        treatment_id=treatment_id,
        artifact_sha256=artifact_sha256,
        runtime_sha256=runtime_sha256,
        workload_sha256=workload_sha256,
        environment_sha256=environment_sha256,
        controls=MappingProxyType(
            {
                "kleidiai.enabled": disabled == "0",
                "threads": threads,
                "instance": instance,
            }
        ),
    )


def _validate_contract_identity(
    contract: Contract,
    comparison: Comparison,
    experiment: Mapping[str, Any],
) -> None:
    validate_comparison_identities(contract, (comparison,))
    declared = {row.treatment_id: row for row in contract.treatments}
    observed = {row.treatment_id: row for row in (comparison.baseline, comparison.treatment)}
    experiment_rows = {row["id"]: row for row in experiment["treatments"]}
    for treatment_id, identity in observed.items():
        expected = declared[treatment_id]
        overrides = {
            key: str(value)
            for key, value in experiment_rows[treatment_id]["environment_overrides"].items()
        }
        if dict(expected.environment) != overrides:
            raise ValueError(f"contract treatment {treatment_id} has mismatched environment")


def _assert_summary_matches(accepted: Mapping[str, Any], derived: Mapping[str, Any]) -> None:
    for mix_id, row in derived["mixes"].items():
        accepted_row = accepted.get("mixes", {}).get(mix_id)
        if not isinstance(accepted_row, dict):
            raise ValueError(f"accepted summary is missing {mix_id}")
        for field, value in row["ratio"].items():
            observed = accepted_row.get("ratio", {}).get(field)
            if not isinstance(observed, (int, float)) or not math.isclose(
                float(observed), float(value), rel_tol=1e-9, abs_tol=1e-9
            ):
                raise ValueError(f"accepted summary disagrees with raw {mix_id} {field}")
    for field, value in derived["quality_comparison"].items():
        observed = accepted.get("quality_comparison", {}).get(field)
        if not isinstance(observed, (int, float)) or not math.isclose(
            float(observed), float(value), rel_tol=1e-9, abs_tol=1e-9
        ):
            raise ValueError(f"accepted summary disagrees with quality rows: {field}")


def _assert_reproduction_inputs_match(
    primary_root: Path,
    reproduction_root: Path,
    primary_experiment: Mapping[str, Any],
    reproduction_experiment: Mapping[str, Any],
    primary_protocol: Mapping[str, Any],
    reproduction_protocol: Mapping[str, Any],
) -> None:
    if reproduction_protocol.get("experiment_id") != reproduction_experiment.get(
        "experiment_id"
    ):
        raise ValueError("reproduction protocol has the wrong experiment identity")
    primary_shape = dict(primary_protocol)
    reproduction_shape = dict(reproduction_protocol)
    primary_shape.pop("experiment_id", None)
    reproduction_shape.pop("experiment_id", None)
    primary_shape["protocol"] = dict(primary_shape.get("protocol", {}))
    reproduction_shape["protocol"] = dict(reproduction_shape.get("protocol", {}))
    primary_shape["protocol"].pop("experiment_id", None)
    reproduction_shape["protocol"].pop("experiment_id", None)
    if primary_shape != reproduction_shape:
        raise ValueError("reproduction protocol differs from the accepted protocol")
    for field in ("workload_ref", "environment_ref"):
        if primary_experiment.get(field) != reproduction_experiment.get(field):
            raise ValueError(f"reproduction {field} differs from accepted evidence")
    if primary_experiment.get("treatments") != reproduction_experiment.get("treatments"):
        raise ValueError("reproduction treatment declarations differ from accepted evidence")

    relative_root = Path("capacity/experiment/capacity")
    primary_files = {
        path.relative_to(primary_root / relative_root): path
        for path in (primary_root / relative_root).rglob("*.jsonl")
    }
    reproduction_files = {
        path.relative_to(reproduction_root / relative_root): path
        for path in (reproduction_root / relative_root).rglob("*.jsonl")
    }
    if set(primary_files) != set(reproduction_files):
        raise ValueError("reproduction request evidence has a different file set")
    for relative, primary_path in primary_files.items():
        primary_ids = [row.response.get("request_id") for row in _samples(primary_path)]
        reproduction_ids = [
            row.response.get("request_id") for row in _samples(reproduction_files[relative])
        ]
        if primary_ids != reproduction_ids or not all(
            isinstance(request_id, str) and request_id for request_id in primary_ids
        ):
            raise ValueError(f"reproduction workload identities differ: {relative}")


def verify_and_derive(
    contract: Contract,
    evidence_root: Path,
    checksums: Path,
    workload_manifest: Path,
    reproduction_root: Path,
    reproduction_checksums: Path,
) -> VerifiedEvidence:
    """Verify integrity, derive metrics, and bind observed identities to a contract."""
    checksum_result = verify_checksum_ledger(checksums, evidence_root)
    if not checksum_result.passed:
        raise ValueError(
            "checksum verification failed: "
            f"missing={checksum_result.missing}, mismatched={checksum_result.mismatched}"
        )
    _verify_workload_manifest(workload_manifest)
    experiment = _json(evidence_root / "experiment.json")
    capacity_protocol = _json(evidence_root / "capacity/experiment/protocol.json")
    if capacity_protocol.get("experiment_id") != experiment.get("experiment_id"):
        raise ValueError("experiment identity differs between protocol and evidence")
    protocol_ids = {
        row.get("treatment_id") for row in capacity_protocol.get("treatments", [])
        if isinstance(row, dict)
    }
    if protocol_ids != set(TREATMENT_IDS):
        raise ValueError("capacity protocol treatment IDs are invalid")

    quality_base = quality_from_dict(
        _json(evidence_root / "capacity/experiment/quality/kleidiai-disabled.json")
    )
    quality_treatment = quality_from_dict(
        _json(evidence_root / "capacity/experiment/quality/kleidiai-enabled.json")
    )
    quality = compare_quality(quality_base, quality_treatment)
    mixes = _derive_capacity(evidence_root, capacity_protocol)
    runtime_sha256 = _sha256(evidence_root / "runtime-lock.json")
    workload_sha256 = _sha256(workload_manifest)
    environment_sha256 = _sha256(evidence_root / "capacity/experiment/environment.json")
    identities = _json(evidence_root / "capacity/artifact-identities.json")
    artifact_sha256 = identities.get("source", {}).get("sha256")
    if not isinstance(artifact_sha256, str):
        raise ValueError("source artifact identity is missing")
    runtime = _json(evidence_root / "runtime-lock.json")
    match = re.search(r"\b(c\w+\.\w+large)\b", str(runtime.get("hardware", "")))
    if not match:
        raise ValueError("instance identity is missing from runtime lock")

    baseline = _identity(
        "kleidiai-disabled",
        experiment,
        artifact_sha256=artifact_sha256,
        runtime_sha256=runtime_sha256,
        workload_sha256=workload_sha256,
        environment_sha256=environment_sha256,
        instance=match.group(1),
    )
    treatment = _identity(
        "kleidiai-enabled",
        experiment,
        artifact_sha256=artifact_sha256,
        runtime_sha256=runtime_sha256,
        workload_sha256=workload_sha256,
        environment_sha256=environment_sha256,
        instance=match.group(1),
    )
    baseline_arm = "kai_" in (evidence_root / "perf-disabled.txt").read_text(
        encoding="utf-8", errors="replace"
    )
    treatment_arm = "kai_" in (evidence_root / "perf-enabled.txt").read_text(
        encoding="utf-8", errors="replace"
    )
    comparison_ids = {claim.comparison_id for claim in contract.claims}
    scopes = {claim.causal_scope for claim in contract.claims}
    if len(comparison_ids) != 1 or scopes != {CausalScope.ARM_ACCELERATION}:
        raise ValueError("reference adapter requires one Arm-acceleration comparison")
    reproduction_checksum_result = verify_checksum_ledger(
        reproduction_checksums, reproduction_root
    )
    if not reproduction_checksum_result.passed:
        raise ValueError(
            "reproduction checksum verification failed: "
            f"missing={reproduction_checksum_result.missing}, "
            f"mismatched={reproduction_checksum_result.mismatched}"
        )
    reproduction_experiment = _json(reproduction_root / "experiment.json")
    if reproduction_experiment.get("causal_scope") != "reproduction":
        raise ValueError("reproduction evidence has the wrong causal scope")
    reproduction_protocol = _json(
        reproduction_root / "capacity/experiment/protocol.json"
    )
    _assert_reproduction_inputs_match(
        evidence_root,
        reproduction_root,
        experiment,
        reproduction_experiment,
        capacity_protocol,
        reproduction_protocol,
    )
    reproduction_mixes = _derive_capacity(reproduction_root, reproduction_protocol)
    reproduction_accepted = _json(
        reproduction_root / "capacity/experiment/summary.json"
    )
    reproduction_quality = compare_quality(
        quality_from_dict(
            _json(
                reproduction_root
                / "capacity/experiment/quality/kleidiai-disabled.json"
            )
        ),
        quality_from_dict(
            _json(
                reproduction_root
                / "capacity/experiment/quality/kleidiai-enabled.json"
            )
        ),
    )
    _assert_summary_matches(
        reproduction_accepted,
        {
            "mixes": reproduction_mixes,
            "quality_comparison": asdict(reproduction_quality),
        },
    )
    reproduction_identities = _json(
        reproduction_root / "capacity/artifact-identities.json"
    )
    if reproduction_identities.get("source", {}).get("sha256") != artifact_sha256:
        raise ValueError("reproduction model artifact differs from accepted evidence")
    if _sha256(reproduction_root / "runtime-lock.json") != runtime_sha256:
        raise ValueError("reproduction runtime differs from accepted evidence")
    reproduction_rows = {
        row["id"]: row for row in reproduction_experiment.get("treatments", [])
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    for treatment_id, declared_treatment in {
        row.treatment_id: row for row in contract.treatments
    }.items():
        observed = reproduction_rows.get(treatment_id, {}).get("environment_overrides")
        if not isinstance(observed, dict) or {
            key: str(value) for key, value in observed.items()
        } != dict(declared_treatment.environment):
            raise ValueError(f"reproduction treatment controls differ: {treatment_id}")
    reproduction_baseline_arm = "kai_" in (
        reproduction_root / "perf-disabled.txt"
    ).read_text(encoding="utf-8", errors="replace")
    reproduction_treatment_arm = "kai_" in (
        reproduction_root / "perf-enabled.txt"
    ).read_text(encoding="utf-8", errors="replace")
    if reproduction_baseline_arm or not reproduction_treatment_arm:
        raise ValueError("reproduction Arm attribution control failed")
    relative_differences = {
        name: abs(row["ratio"]["ratio"] - mixes[name]["ratio"]["ratio"])
        / mixes[name]["ratio"]["ratio"]
        for name, row in reproduction_mixes.items()
    }

    metrics = {
        "minimum_capacity_ratio": min(row["ratio"]["ratio"] for row in mixes.values()),
        **{f"{name}_capacity_ratio": row["ratio"]["ratio"] for name, row in mixes.items()},
        "accuracy_delta_pp": quality.accuracy_delta_pp,
        "macro_f1_delta_pp": quality.macro_f1_delta_pp,
        "schema_valid_rate": quality.schema_valid_rate,
        "guard_queue_accuracy": _operational_queue_accuracy(
            workload_manifest, quality_treatment.rows
        ),
        "enabled_kai_callchains_observed": float(treatment_arm),
        "reproduction_max_relative_difference": max(relative_differences.values()),
    }
    comparison = Comparison(
        comparison_id=next(iter(comparison_ids)),
        causal_scope=CausalScope.ARM_ACCELERATION,
        baseline=baseline,
        treatment=treatment,
        metrics=MappingProxyType(metrics),
        evidence_kinds=frozenset(
            {
                "request_samples", "boundary_confirmations", "quality_rows",
                "artifact_hashes", "arm_callchains", "reproduction",
            }
        ),
        arm_path_baseline_observed=baseline_arm,
        arm_path_treatment_observed=treatment_arm,
    )
    _validate_contract_identity(contract, comparison, experiment)

    acceptance = experiment.get("acceptance", {})
    passing_mixes = sum(
        row["valid_boundary_confirmations"]
        and row["ratio"]["ratio"] >= float(acceptance["minimum_ratio"])
        and row["ratio"]["lower_95"] >= float(acceptance["minimum_lower_95"])
        for row in mixes.values()
    )
    quality_payload = asdict(quality)
    quality_passed = (
        quality.accuracy_delta_pp >= -float(acceptance["maximum_accuracy_loss_pp"])
        and quality.macro_f1_delta_pp >= -float(acceptance["maximum_macro_f1_loss_pp"])
        and quality.schema_valid_rate >= float(acceptance["minimum_schema_valid_rate"])
    )
    accepted_summary = _json(evidence_root / "capacity/experiment/summary.json")
    summary = {
        "schema_version": "1.0.0",
        "experiment_id": experiment["experiment_id"],
        "quality_passed": quality_passed,
        "passing_mixes": passing_mixes,
        "passed": quality_passed and passing_mixes >= int(acceptance["minimum_passing_mixes"]),
        "mixes": mixes,
        "quality_comparison": quality_payload,
        "elapsed_seconds": accepted_summary.get("elapsed_seconds"),
        "reproduction": {
            "experiment_id": reproduction_experiment["experiment_id"],
            "maximum_relative_difference": max(relative_differences.values()),
            "mixes": {
                name: {
                    "reference_ratio": mixes[name]["ratio"]["ratio"],
                    "reproduction_ratio": reproduction_mixes[name]["ratio"]["ratio"],
                    "relative_difference": difference,
                }
                for name, difference in relative_differences.items()
            },
        },
    }
    _assert_summary_matches(accepted_summary, summary)
    return VerifiedEvidence(
        comparison=comparison,
        summary=MappingProxyType(summary),
        checksums=checksum_result,
        reproduction_checksums=reproduction_checksum_result,
    )
