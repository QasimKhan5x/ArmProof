"""Verify and derive the profile-guided Graviton memory optimization."""

from __future__ import annotations

import hashlib
import json
import statistics
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class TuningArchive:
    experiment_id: str
    archive_sha256: str
    internal_checksummed_files: int
    experiment: Mapping[str, Any]
    protocol: Mapping[str, Any]
    summary: Mapping[str, Any]
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
        observed_ids = {
            experiment.get("experiment_id"),
            protocol.get("experiment_id"),
            summary.get("experiment_id"),
        }
        if observed_ids != {expected_experiment_id}:
            raise ValueError("runtime memory experiment identities differ")
        return TuningArchive(
            experiment_id=expected_experiment_id,
            archive_sha256=observed_sha256,
            internal_checksummed_files=checked,
            experiment=MappingProxyType(experiment),
            protocol=MappingProxyType(protocol),
            summary=MappingProxyType(summary),
            thp_before=read("evidence/thp-before.txt").decode("utf-8").strip(),
            thp_after=read("evidence/thp-after.txt").decode("utf-8").strip(),
        )


def _rows(archive: TuningArchive, phase: str, variant_id: str) -> list[dict[str, Any]]:
    rows = archive.summary.get("rows")
    if not isinstance(rows, list):
        raise ValueError("runtime memory summary has no rows")
    selected = [
        row for row in rows
        if isinstance(row, dict)
        and row.get("phase") == phase
        and row.get("variant_id") == variant_id
    ]
    return sorted(selected, key=lambda row: int(row["repetition"]))


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

    simplification_variants = simplification.summary.get("variants")
    simplified_variant = {
        "id": "mimalloc-thp",
        "session": {},
        "mimalloc": True,
        "thp": "always",
    }
    if simplification_variants != [simplified_variant]:
        raise ValueError("runtime memory simplification archive uses the wrong recipe")
    if simplification.protocol.get("variant_set") != "simplified-confirmation":
        raise ValueError("runtime memory simplification protocol is invalid")

    baseline_rows = _rows(sustained, "confirmation", "current")
    optimized_rows = _rows(sustained, "confirmation", "thread-memory")
    simplified_rows = _rows(simplification, "confirmation", "mimalloc-thp")
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
        raise ValueError("runtime memory simplification is not the frozen sustained rejection")

    isolation_medians: dict[str, float] = {}
    for variant_id in ("current", "thp-only", "thread-thp", "mimalloc-thp"):
        rows = _rows(isolation, "screen", variant_id)
        if len(rows) != 2:
            raise ValueError(f"runtime memory ablation is incomplete: {variant_id}")
        isolation_medians[variant_id] = _median_p95(rows)
    if not (
        isolation_medians["mimalloc-thp"] < isolation_medians["thp-only"]
        and isolation_medians["thread-thp"] >= isolation_medians["thp-only"]
    ):
        raise ValueError("runtime memory ablation does not reproduce the frozen short-screen ranking")

    baseline_p95 = tuple(float(row["summary"]["p95_ms"]) for row in baseline_rows)
    optimized_p95 = tuple(float(row["summary"]["p95_ms"]) for row in optimized_rows)
    simplification_p95 = tuple(
        float(row["summary"]["p95_ms"]) for row in simplified_rows
    )
    baseline_median = float(statistics.median(baseline_p95))
    optimized_median = float(statistics.median(optimized_p95))
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
        recipe=MappingProxyType({
            "arm_compute": "KleidiAI I8MM",
            "allocator": "mimalloc",
            "transparent_huge_pages": "always",
            "onnxruntime_thread_overrides": {
                "session.dynamic_block_base": "4",
                "session.intra_op.spin_backoff_max": "8",
                "session.intra_op.spin_duration_us": "1000",
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
