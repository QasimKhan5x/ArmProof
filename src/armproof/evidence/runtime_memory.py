"""Verify and derive the profile-guided Graviton memory optimization."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import tarfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Mapping

from armproof.workload.io import summary_to_dict
from armproof.workload.load import RequestSample, summarize_samples


THREAD_OPTIONS = {
    "session.dynamic_block_base": "4",
    "session.intra_op.spin_backoff_max": "8",
    "session.intra_op.spin_duration_us": "1000",
}

BASE_SESSION_OPTIONS = {
    "log_id": "onnxruntime-genai",
    "mlas.disable_kleidiai": "0",
    "provider_options": [],
}

EXPECTED_VARIANTS: dict[str, tuple[dict[str, Any], ...]] = {
    "EXP-2026-015": (
        {"id": "current", "session": {}, "mimalloc": False, "thp": "madvise"},
        {
            "id": "thread-tuned",
            "session": THREAD_OPTIONS,
            "mimalloc": False,
            "thp": "madvise",
        },
        {"id": "mimalloc", "session": {}, "mimalloc": True, "thp": "madvise"},
        {
            "id": "thread-memory",
            "session": THREAD_OPTIONS,
            "mimalloc": True,
            "thp": "always",
        },
    ),
    "EXP-2026-016": (
        {"id": "current", "session": {}, "mimalloc": False, "thp": "madvise"},
        {"id": "thp-only", "session": {}, "mimalloc": False, "thp": "always"},
        {
            "id": "thread-thp",
            "session": THREAD_OPTIONS,
            "mimalloc": False,
            "thp": "always",
        },
        {"id": "mimalloc-thp", "session": {}, "mimalloc": True, "thp": "always"},
    ),
    "EXP-2026-017": (
        {"id": "mimalloc-thp", "session": {}, "mimalloc": True, "thp": "always"},
    ),
}


@dataclass(frozen=True)
class TuningArchive:
    experiment_id: str
    archive_sha256: str
    internal_checksummed_files: int
    experiment: Mapping[str, Any]
    protocol: Mapping[str, Any]
    summary: Mapping[str, Any]
    raw_windows: Mapping[str, tuple[Mapping[str, Any], ...]]
    window_summaries: Mapping[str, Mapping[str, Any]]
    variant_configs: Mapping[str, Mapping[str, Any]]
    thp_before: str
    thp_after: str


@dataclass(frozen=True)
class RuntimeMemoryAudit:
    passed: bool
    sustained_experiment_id: str
    isolation_experiment_id: str
    simplification_experiment_id: str
    candidate_rps: float
    previous_capacity_rps: float
    capacity_gain_percent: float
    baseline_p95_ms: tuple[float, ...]
    optimized_p95_ms: tuple[float, ...]
    baseline_median_p95_ms: float
    optimized_median_p95_ms: float
    p95_reduction_percent: float
    confirmation_passes: int
    confirmation_windows: int
    simplification_failures: int
    simplification_windows: int
    simplification_p95_ms: tuple[float, ...]
    simplification_median_p95_ms: float
    output_digest: str
    raw_output_digest: str
    raw_output_cases: int
    raw_output_rows: int
    complete_raw_windows: int
    complete_raw_rows: int
    sustained_equivalence_cases: int
    sustained_equivalence_rows: int
    recipe: Mapping[str, Any]
    ablation_median_p95_ms: Mapping[str, float]
    internal_checksummed_files: int
    archive_sha256: Mapping[str, str]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _json(payload: bytes, field: str) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError(f"runtime memory {field} must contain an object")
    return value


def _jsonl(payload: bytes, field: str) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for line_number, line in enumerate(payload.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(
                f"runtime memory {field} line {line_number} must contain an object"
            )
        rows.append(MappingProxyType(value))
    if not rows:
        raise ValueError(f"runtime memory {field} contains no request rows")
    return tuple(rows)


def verify_tuning_archive(
    archive_path: Path,
    *,
    expected_sha256: str,
    expected_experiment_id: str,
) -> TuningArchive:
    """Verify one immutable tuning archive without extracting it."""

    observed_sha256 = _sha256(archive_path.read_bytes())
    if observed_sha256 != expected_sha256:
        raise ValueError("runtime memory archive SHA-256 mismatch")
    with tarfile.open(archive_path, "r:gz") as archive:
        members: dict[str, tarfile.TarInfo] = {}
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("runtime memory archive contains an unsafe path")
            if member.isfile():
                if member.name in members:
                    raise ValueError("runtime memory archive contains duplicate paths")
                members[member.name] = member

        def read(name: str) -> bytes:
            member = members.get(name)
            if member is None:
                raise ValueError(f"runtime memory archive is missing {name}")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f"runtime memory archive cannot read {name}")
            return stream.read()

        ledger = read("evidence/SHA256SUMS").decode("utf-8")
        checked = 0
        declared_paths: set[str] = set()
        for line in ledger.splitlines():
            digest, separator, absolute = line.partition("  ")
            if separator != "  " or not absolute.startswith("/opt/armproof/evidence/"):
                raise ValueError("runtime memory checksum ledger is malformed")
            relative = "evidence/" + absolute.removeprefix("/opt/armproof/evidence/")
            if relative in declared_paths:
                raise ValueError("runtime memory checksum ledger contains duplicates")
            declared_paths.add(relative)
            if _sha256(read(relative)) != digest:
                raise ValueError(f"runtime memory checksum mismatch: {relative}")
            checked += 1
        if set(members) - {"evidence/SHA256SUMS"} != declared_paths:
            raise ValueError("runtime memory archive and checksum ledger differ")

        if read("evidence/exit-status.txt").decode("utf-8").strip() != "0":
            raise ValueError("runtime memory guest did not exit successfully")
        experiment = _json(read("evidence/experiment.json"), "experiment")
        protocol = _json(read("evidence/protocol.json"), "protocol")
        summary = _json(read("evidence/tuning/summary.json"), "summary")
        raw_windows = {
            name: _jsonl(read(name), name)
            for name in sorted(declared_paths)
            if name.startswith("evidence/tuning/") and name.endswith(".jsonl")
        }
        if not raw_windows:
            raise ValueError("runtime memory archive contains no raw request windows")
        window_summaries = {
            name: MappingProxyType(_json(read(name), name))
            for name in sorted(declared_paths)
            if name.startswith("evidence/tuning/")
            and name.endswith(".summary.json")
        }
        variant_configs: dict[str, Mapping[str, Any]] = {}
        for name in sorted(declared_paths):
            path = PurePosixPath(name)
            if (
                len(path.parts) == 5
                and path.parts[:3] == ("evidence", "tuning", "variants")
                and path.name == "genai_config.json"
            ):
                variant_configs[path.parts[3]] = MappingProxyType(
                    _json(read(name), name)
                )
        observed_ids = {
            experiment.get("experiment_id"),
            protocol.get("experiment_id"),
            summary.get("experiment_id"),
        }
        if observed_ids != {expected_experiment_id}:
            raise ValueError("runtime memory experiment identities differ")
        result = TuningArchive(
            experiment_id=expected_experiment_id,
            archive_sha256=observed_sha256,
            internal_checksummed_files=checked,
            experiment=MappingProxyType(experiment),
            protocol=MappingProxyType(protocol),
            summary=MappingProxyType(summary),
            raw_windows=MappingProxyType(raw_windows),
            window_summaries=MappingProxyType(window_summaries),
            variant_configs=MappingProxyType(variant_configs),
            thp_before=read("evidence/thp-before.txt").decode("utf-8").strip(),
            thp_after=read("evidence/thp-after.txt").decode("utf-8").strip(),
        )
    _verify_all_window_summaries(result)
    _validate_variant_configs(result)
    return result


def _aggregate_rows(archive: TuningArchive) -> list[dict[str, Any]]:
    rows = archive.summary.get("rows")
    if not isinstance(rows, list):
        raise ValueError("runtime memory summary has no rows")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("runtime memory summary contains a non-object row")
    return [dict(row) for row in rows]


def _window_identity(row: Mapping[str, Any]) -> tuple[str, str, int]:
    try:
        phase = str(row["phase"])
        variant_id = str(row["variant_id"])
        repetition = int(row["repetition"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("runtime memory window identity is invalid") from exc
    if phase not in {"screen", "confirmation"} or not variant_id or repetition < 1:
        raise ValueError("runtime memory window identity is invalid")
    return phase, variant_id, repetition


def _raw_window_path(identity: tuple[str, str, int]) -> str:
    phase, variant_id, repetition = identity
    return f"evidence/tuning/{phase}/{variant_id}/rep-{repetition}.jsonl"


def _summary_window_path(identity: tuple[str, str, int]) -> str:
    return _raw_window_path(identity).removesuffix(".jsonl") + ".summary.json"


def _expected_window_identities(
    archive: TuningArchive,
) -> set[tuple[str, str, int]]:
    expected_variants = EXPECTED_VARIANTS.get(archive.experiment_id)
    if expected_variants is None:
        raise ValueError("runtime memory archive uses an unexpected experiment")
    variants = [row["id"] for row in expected_variants]
    protocol = archive.protocol
    if archive.experiment_id == "EXP-2026-015":
        phases = {
            "screen": variants,
            "confirmation": ["current", "thread-memory"],
        }
    elif archive.experiment_id == "EXP-2026-016":
        phases = {"screen": variants}
    else:
        phases = {"confirmation": variants}
    expected: set[tuple[str, str, int]] = set()
    for phase, phase_variants in phases.items():
        repetitions = int(protocol[f"{phase}_repetitions"])
        expected.update(
            (phase, variant_id, repetition)
            for variant_id in phase_variants
            for repetition in range(1, repetitions + 1)
        )
    return expected


def _request_sample(row: Mapping[str, Any], field: str) -> RequestSample:
    try:
        sample = RequestSample(
            request_id=str(row["request_id"]),
            scheduled_ns=int(row["scheduled_ns"]),
            started_ns=int(row["started_ns"]),
            finished_ns=int(row["finished_ns"]),
            status_code=(
                None if row.get("status_code") is None else int(row["status_code"])
            ),
            error=None if row.get("error") is None else str(row["error"]),
            response=(
                row.get("response") if isinstance(row.get("response"), dict) else None
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"runtime memory raw request is invalid: {field}") from exc
    stored_latency = row.get("latency_ms")
    if not isinstance(stored_latency, (int, float)) or not math.isclose(
        float(stored_latency), sample.latency_ms, rel_tol=1e-12, abs_tol=1e-6
    ):
        raise ValueError(f"runtime memory raw latency disagrees with timestamps: {field}")
    return sample


def _same_number(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-6)
    return left == right


def _verify_all_window_summaries(archive: TuningArchive) -> list[dict[str, Any]]:
    """Re-derive every aggregate and per-window summary from raw request rows."""

    rows = _aggregate_rows(archive)
    identities = [_window_identity(row) for row in rows]
    if len(identities) != len(set(identities)):
        raise ValueError("runtime memory summary contains duplicate windows")
    expected_identities = _expected_window_identities(archive)
    if set(identities) != expected_identities:
        raise ValueError("runtime memory summary window matrix is incomplete")
    expected_raw = {_raw_window_path(identity) for identity in expected_identities}
    expected_summaries = {
        _summary_window_path(identity) for identity in expected_identities
    }
    if set(archive.raw_windows) != expected_raw:
        raise ValueError("runtime memory raw window set differs from the protocol")
    if set(archive.window_summaries) != expected_summaries:
        raise ValueError("runtime memory per-window summary set differs from the protocol")

    variants = {
        row["id"]: row for row in EXPECTED_VARIANTS[archive.experiment_id]
    }
    for row, identity in zip(rows, identities, strict=True):
        phase, variant_id, _ = identity
        field = _raw_window_path(identity)
        summary_field = _summary_window_path(identity)
        if dict(archive.window_summaries[summary_field]) != row:
            raise ValueError(
                f"runtime memory per-window summary disagrees with aggregate: {summary_field}"
            )
        raw = archive.raw_windows.get(field)
        if raw is None:
            raise ValueError(f"runtime memory archive is missing {field}")
        samples = tuple(_request_sample(item, field) for item in raw)
        if len({sample.request_id for sample in samples}) != len(samples):
            raise ValueError(f"runtime memory raw window contains duplicate requests: {field}")
        seconds = float(row["seconds"])
        target_rps = float(row["target_rps"])
        if seconds != float(archive.protocol[f"{phase}_seconds"]):
            raise ValueError(f"runtime memory window duration differs: {field}")
        if target_rps != float(archive.protocol["candidate_rps"]):
            raise ValueError(f"runtime memory target rate differs: {field}")
        if len(samples) != round(target_rps * seconds):
            raise ValueError(f"runtime memory raw request count differs: {field}")
        derived = summary_to_dict(summarize_samples(samples, seconds))
        stored = row.get("summary")
        if not isinstance(stored, dict) or set(stored) != set(derived) or any(
            not _same_number(stored[key], derived[key]) for key in derived
        ):
            raise ValueError(f"runtime memory stored summary disagrees with raw rows: {field}")
        protocol = archive.protocol
        passed = bool(
            derived["p95_ms"] is not None
            and float(derived["p95_ms"]) <= float(protocol["p95_slo_ms"])
            and float(derived["error_rate"]) <= float(protocol["max_error_rate"])
            and float(derived["accepted_rps"])
            >= target_rps * float(protocol["minimum_delivery_ratio"])
        )
        if row.get("passed") is not passed:
            raise ValueError(f"runtime memory stored decision disagrees with raw rows: {field}")
        if row.get("thp_mode") != variants[variant_id]["thp"]:
            raise ValueError(f"runtime memory THP readback differs from declaration: {field}")
    return sorted(rows, key=_window_identity)


def _rows(
    rows: list[dict[str, Any]], phase: str, variant_id: str
) -> list[dict[str, Any]]:
    return sorted(
        [
            row
            for row in rows
            if row.get("phase") == phase and row.get("variant_id") == variant_id
        ],
        key=lambda row: int(row["repetition"]),
    )


def _validate_variant_configs(archive: TuningArchive) -> dict[str, Any]:
    expected_variants = EXPECTED_VARIANTS.get(archive.experiment_id)
    if expected_variants is None or archive.summary.get("variants") != list(
        expected_variants
    ):
        raise ValueError("runtime memory archive uses the wrong declared variants")
    expected_ids = {row["id"] for row in expected_variants}
    if set(archive.variant_configs) != expected_ids:
        raise ValueError("runtime memory variant config set is incomplete")

    normalized_configs: list[dict[str, Any]] = []
    threads = int(archive.protocol["threads"])
    for variant in expected_variants:
        variant_id = variant["id"]
        config = deepcopy(dict(archive.variant_configs[variant_id]))
        try:
            options = config["model"]["decoder"]["session_options"]
        except (KeyError, TypeError) as exc:
            raise ValueError(
                f"runtime memory variant config is malformed: {variant_id}"
            ) from exc
        if not isinstance(options, dict):
            raise ValueError(f"runtime memory variant config is malformed: {variant_id}")
        expected_options = {
            **BASE_SESSION_OPTIONS,
            "intra_op_num_threads": threads,
            **variant["session"],
        }
        if options != expected_options:
            raise ValueError(
                f"runtime memory variant config disagrees with declaration: {variant_id}"
            )
        for key in THREAD_OPTIONS:
            options.pop(key, None)
        normalized_configs.append(config)
    if any(config != normalized_configs[0] for config in normalized_configs[1:]):
        raise ValueError("runtime memory variant configs differ beyond declared options")
    return normalized_configs[0]


def _raw_output_map(
    archive: TuningArchive,
    rows: list[dict[str, Any]],
    phase: str,
    variant_id: str,
) -> tuple[dict[str, str], int]:
    outputs: dict[str, str] = {}
    row_count = 0
    for row in _rows(rows, phase, variant_id):
        repetition = int(row["repetition"])
        field = f"evidence/tuning/{phase}/{variant_id}/rep-{repetition}.jsonl"
        for raw in archive.raw_windows[field]:
            sample = _request_sample(raw, field)
            response = sample.response
            if not sample.accepted or not isinstance(response, Mapping):
                raise ValueError(f"runtime memory output row was not accepted: {field}")
            request_id = response.get("request_id")
            output = response.get("output")
            if not isinstance(request_id, str) or not isinstance(output, str):
                raise ValueError(f"runtime memory output identity is incomplete: {field}")
            if request_id in outputs and outputs[request_id] != output:
                raise ValueError(
                    f"runtime memory output changed between repetitions: {request_id}"
                )
            outputs[request_id] = output
            row_count += 1
    return outputs, row_count


def _median_p95(rows: list[dict[str, Any]]) -> float:
    return float(statistics.median(float(row["summary"]["p95_ms"]) for row in rows))


def derive_runtime_memory_audit(
    sustained: TuningArchive,
    isolation: TuningArchive,
    simplification: TuningArchive,
    *,
    previous_capacity_rps: float,
    expected_output_digest: str,
) -> RuntimeMemoryAudit:
    """Bind the ablation and sustained confirmation into one release condition."""

    if (
        sustained.experiment_id != "EXP-2026-015"
        or isolation.experiment_id != "EXP-2026-016"
        or simplification.experiment_id != "EXP-2026-017"
    ):
        raise ValueError("runtime memory evidence uses unexpected experiments")
    if sustained.thp_before != sustained.thp_after or isolation.thp_before != isolation.thp_after:
        raise ValueError("runtime memory experiment did not restore THP state")
    if simplification.thp_before != simplification.thp_after:
        raise ValueError("runtime memory simplification did not restore THP state")

    sustained_config = _validate_variant_configs(sustained)
    isolation_config = _validate_variant_configs(isolation)
    simplification_config = _validate_variant_configs(simplification)
    if not (sustained_config == isolation_config == simplification_config):
        raise ValueError("runtime memory archives use different base model configs")
    if simplification.protocol.get("variant_set") != "simplified-confirmation":
        raise ValueError("runtime memory simplification protocol is invalid")

    sustained_rows = _verify_all_window_summaries(sustained)
    isolation_rows = _verify_all_window_summaries(isolation)
    simplification_rows = _verify_all_window_summaries(simplification)
    baseline_rows = _rows(sustained_rows, "confirmation", "current")
    optimized_rows = _rows(sustained_rows, "confirmation", "thread-memory")
    simplified_rows = _rows(
        simplification_rows, "confirmation", "mimalloc-thp"
    )
    expected_windows = int(sustained.protocol["confirmation_repetitions"])
    simplification_windows = int(simplification.protocol["confirmation_repetitions"])
    candidate_rps = float(sustained.protocol["candidate_rps"])
    p95_slo_ms = float(sustained.protocol["p95_slo_ms"])
    if len(baseline_rows) != 5 or any(bool(row["passed"]) for row in baseline_rows):
        raise ValueError("runtime memory baseline is not the frozen five-window failure")
    if (
        sustained.summary.get("accepted") is not True
        or sustained.summary.get("winner") != "thread-memory"
        or sustained.summary.get("outputs_equivalent") is not True
    ):
        raise ValueError("runtime memory sustained archive did not accept the full recipe")
    if len(optimized_rows) != expected_windows:
        raise ValueError("runtime memory sustained window count differs")
    if any(float(row["target_rps"]) != candidate_rps for row in optimized_rows):
        raise ValueError("runtime memory sustained run changed the candidate rate")
    if any(
        not bool(row["passed"])
        or float(row["summary"]["p95_ms"]) > p95_slo_ms
        or float(row["summary"]["error_rate"]) != 0.0
        or row["thp_mode"] != "always"
        for row in optimized_rows
    ):
        raise ValueError("runtime memory full recipe did not pass every release rule")
    output_digests = sustained.summary.get("output_digests")
    if (
        not isinstance(output_digests, dict)
        or output_digests.get("thread-memory") != expected_output_digest
        or output_digests.get("current") != expected_output_digest
    ):
        raise ValueError("runtime memory sustained output identity differs")

    simplified_digest = simplification.summary.get("output_digests")
    simplification_slo_ms = float(simplification.protocol["p95_slo_ms"])
    if (
        len(simplified_rows) != simplification_windows
        or simplification.summary.get("accepted") is not False
        or simplification.summary.get("outputs_equivalent") is not True
        or not isinstance(simplified_digest, dict)
        or simplified_digest.get("mimalloc-thp") != expected_output_digest
        or any(bool(row["passed"]) for row in simplified_rows)
        or any(float(row["summary"]["error_rate"]) != 0.0 for row in simplified_rows)
        or any(float(row["summary"]["p95_ms"]) <= simplification_slo_ms for row in simplified_rows)
    ):
        raise ValueError("runtime memory simplification is not the archived sustained rejection")

    baseline_outputs, baseline_output_rows = _raw_output_map(
        sustained, sustained_rows, "confirmation", "current"
    )
    optimized_outputs, optimized_output_rows = _raw_output_map(
        sustained, sustained_rows, "confirmation", "thread-memory"
    )
    simplified_outputs, simplified_output_rows = _raw_output_map(
        simplification, simplification_rows, "confirmation", "mimalloc-thp"
    )
    if not baseline_outputs or not (
        baseline_outputs == optimized_outputs == simplified_outputs
    ):
        raise ValueError("runtime memory raw outputs differ between sustained treatments")
    raw_output_digest = _sha256(
        json.dumps(
            baseline_outputs, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )

    isolation_medians: dict[str, float] = {}
    for variant_id in ("current", "thp-only", "thread-thp", "mimalloc-thp"):
        rows = _rows(isolation_rows, "screen", variant_id)
        if len(rows) != 2:
            raise ValueError(f"runtime memory ablation is incomplete: {variant_id}")
        isolation_medians[variant_id] = _median_p95(rows)
    if not (
        isolation_medians["mimalloc-thp"] < isolation_medians["thp-only"]
        and isolation_medians["thread-thp"] >= isolation_medians["thp-only"]
    ):
        raise ValueError(
            "runtime memory ablation does not reproduce the frozen short-screen ranking"
        )

    baseline_p95 = tuple(float(row["summary"]["p95_ms"]) for row in baseline_rows)
    optimized_p95 = tuple(float(row["summary"]["p95_ms"]) for row in optimized_rows)
    simplification_p95 = tuple(
        float(row["summary"]["p95_ms"]) for row in simplified_rows
    )
    baseline_median = float(statistics.median(baseline_p95))
    optimized_median = float(statistics.median(optimized_p95))
    complete_raw_windows = sum(
        len(archive.raw_windows) for archive in (sustained, isolation, simplification)
    )
    complete_raw_rows = sum(
        len(rows)
        for archive in (sustained, isolation, simplification)
        for rows in archive.raw_windows.values()
    )
    sustained_equivalence_rows = (
        baseline_output_rows + optimized_output_rows + simplified_output_rows
    )
    return RuntimeMemoryAudit(
        passed=True,
        sustained_experiment_id=sustained.experiment_id,
        isolation_experiment_id=isolation.experiment_id,
        simplification_experiment_id=simplification.experiment_id,
        candidate_rps=candidate_rps,
        previous_capacity_rps=previous_capacity_rps,
        capacity_gain_percent=(candidate_rps / previous_capacity_rps - 1.0) * 100,
        baseline_p95_ms=baseline_p95,
        optimized_p95_ms=optimized_p95,
        baseline_median_p95_ms=baseline_median,
        optimized_median_p95_ms=optimized_median,
        p95_reduction_percent=(baseline_median - optimized_median) / baseline_median * 100,
        confirmation_passes=sum(bool(row["passed"]) for row in optimized_rows),
        confirmation_windows=expected_windows,
        simplification_failures=sum(not bool(row["passed"]) for row in simplified_rows),
        simplification_windows=simplification_windows,
        simplification_p95_ms=simplification_p95,
        simplification_median_p95_ms=float(statistics.median(simplification_p95)),
        output_digest=expected_output_digest,
        raw_output_digest=raw_output_digest,
        raw_output_cases=len(baseline_outputs),
        raw_output_rows=sustained_equivalence_rows,
        complete_raw_windows=complete_raw_windows,
        complete_raw_rows=complete_raw_rows,
        sustained_equivalence_cases=len(baseline_outputs),
        sustained_equivalence_rows=sustained_equivalence_rows,
        recipe=MappingProxyType({
            "arm_compute": "KleidiAI I8MM",
            "allocator": "mimalloc",
            "transparent_huge_pages": "always",
            "onnxruntime_thread_overrides": dict(THREAD_OPTIONS),
            "settings_status": "declared_recipe_with_field_level_evidence",
            "setting_evidence": {
                "arm_compute": (
                    "kleidiai_enablement_in_config_i8mm_not_reprofiled_in_stage3"
                ),
                "allocator": "declared_variant_metadata_only",
                "transparent_huge_pages": (
                    "declared_variant_metadata_and_observed_per_window_sysfs"
                ),
                "onnxruntime_thread_overrides": "archived_exact_genai_configs",
            },
            "observed_host_state": {
                "allocator": None,
                "allocator_evidence": "not_observed_no_proc_maps_archived",
                "transparent_huge_pages": "always",
                "transparent_huge_pages_evidence": (
                    "validated_per_window_sysfs_readback"
                ),
            },
            "evidence_counts": {
                "complete_raw_windows": complete_raw_windows,
                "complete_raw_rows": complete_raw_rows,
                "sustained_equivalence_cases": len(baseline_outputs),
                "sustained_equivalence_rows": sustained_equivalence_rows,
            },
        }),
        ablation_median_p95_ms=MappingProxyType(isolation_medians),
        internal_checksummed_files=(
            sustained.internal_checksummed_files
            + isolation.internal_checksummed_files
            + simplification.internal_checksummed_files
        ),
        archive_sha256=MappingProxyType({
            sustained.experiment_id: sustained.archive_sha256,
            isolation.experiment_id: isolation.archive_sha256,
            simplification.experiment_id: simplification.archive_sha256,
        }),
    )
