"""Fail-closed verification of raw BANKING77 quality evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from armproof.evidence.checksums import checksum_ledger_paths, verify_checksum_ledger
from armproof.quality.banking77 import (
    QualityComparison,
    QualityResult,
    compare_quality,
    evaluate_quality,
    load_quality_cases,
    quality_from_dict,
)
from armproof.workload.io import sample_to_dict
from armproof.workload.load import RequestSample


_QUALITY_BATCH = Path("capacity/quality-batch")
_QUALITY_REANALYSIS = Path("capacity/quality-reanalysis")
_EXPECTED_ROWS = 770
_LANES = {
    "disabled": ("kleidiai-disabled", "kleidiai-disabled-samples.jsonl", "kleidiai-disabled.json"),
    "enabled": ("kleidiai-enabled", "kleidiai-enabled-samples.jsonl", "kleidiai-enabled.json"),
}
_RESPONSE_FIELDS = frozenset(
    {"backend", "output", "output_tokens", "prompt_tokens", "request_id"}
)
_SAMPLE_FIELDS = frozenset(
    sample_to_dict(
        RequestSample(
            request_id="schema",
            scheduled_ns=0,
            started_ns=0,
            finished_ns=0,
            status_code=None,
            error=None,
            response=None,
        )
    )
)


@dataclass(frozen=True)
class RawQualitySummary:
    """Checksum-bound quality results independently derived from raw responses."""

    checksummed_files: int
    dataset_rows: int
    disabled_rows: int
    enabled_rows: int
    disabled_quality: QualityResult
    enabled_quality: QualityResult
    comparison: QualityComparison


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read valid JSON from {path}: {exc}") from exc


def _require_integer(value: Any, field: str, line_number: int) -> int:
    if type(value) is not int:
        raise ValueError(f"raw sample line {line_number} has invalid {field}")
    return value


def _parse_sample(row: Any, *, line_number: int, backend: str) -> RequestSample:
    if not isinstance(row, dict) or frozenset(row) != _SAMPLE_FIELDS:
        raise ValueError(f"raw sample line {line_number} does not match sample_to_dict schema")

    request_id = row["request_id"]
    if not isinstance(request_id, str) or not request_id:
        raise ValueError(f"raw sample line {line_number} has invalid request_id")
    scheduled_ns = _require_integer(row["scheduled_ns"], "scheduled_ns", line_number)
    started_ns = _require_integer(row["started_ns"], "started_ns", line_number)
    finished_ns = _require_integer(row["finished_ns"], "finished_ns", line_number)
    if scheduled_ns < 0 or started_ns < scheduled_ns or finished_ns < started_ns:
        raise ValueError(f"raw sample line {line_number} has inconsistent timestamps")

    latency_ms = row["latency_ms"]
    if type(latency_ms) is not float:
        raise ValueError(f"raw sample line {line_number} has invalid latency_ms")
    status_code = row["status_code"]
    if type(status_code) is not int:
        raise ValueError(f"raw sample line {line_number} has invalid status_code")
    error = row["error"]
    if error is not None:
        raise ValueError(f"raw sample line {line_number} was not accepted")

    response = row["response"]
    if not isinstance(response, dict) or frozenset(response) != _RESPONSE_FIELDS:
        raise ValueError(f"raw sample line {line_number} has invalid response schema")
    if not isinstance(response.get("output"), str):
        raise ValueError(f"raw sample line {line_number} has no string output")
    if response.get("backend") != backend:
        raise ValueError(f"raw sample line {line_number} has incorrect backend")
    if response.get("request_id") != request_id:
        raise ValueError(f"raw sample line {line_number} has mismatched response request_id")
    for field in ("output_tokens", "prompt_tokens"):
        if type(response[field]) is not int or response[field] < 0:
            raise ValueError(f"raw sample line {line_number} has invalid {field}")

    sample = RequestSample(
        request_id=request_id,
        scheduled_ns=scheduled_ns,
        started_ns=started_ns,
        finished_ns=finished_ns,
        status_code=status_code,
        error=error,
        response=response,
    )
    if not sample.accepted:
        raise ValueError(f"raw sample line {line_number} was not accepted")
    if sample.latency_ms != latency_ms or sample_to_dict(sample) != row:
        raise ValueError(f"raw sample line {line_number} has inconsistent latency_ms")
    return sample


def _load_samples(path: Path, *, backend: str, expected_rows: int) -> tuple[RequestSample, ...]:
    samples: list[RequestSample] = []
    seen: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"cannot read raw samples from {path}: {exc}") from exc
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            raise ValueError(f"raw sample line {line_number} is blank")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid raw sample JSON on line {line_number}: {exc}") from exc
        sample = _parse_sample(row, line_number=line_number, backend=backend)
        if sample.request_id in seen:
            raise ValueError(f"duplicate raw sample request_id: {sample.request_id}")
        seen.add(sample.request_id)
        samples.append(sample)
    if len(samples) != expected_rows:
        raise ValueError(f"raw sample row count is {len(samples)}; expected {expected_rows}")
    return tuple(samples)


def verify_raw_quality_evidence(
    evidence_root: Path,
    quality_dataset: Path,
    *,
    checksum_ledger: Path | None = None,
    expected_ledger_sha256: str | None = None,
    expected_experiment_id: str | None = None,
    expected_artifact_sha256: str | None = None,
    expected_runtime_sha256: str | None = None,
    source_prefix: str = "/opt/armproof/evidence",
) -> RawQualitySummary:
    """Verify and independently re-evaluate checksum-bound raw quality evidence."""
    evidence_root = Path(evidence_root)
    quality_dataset = Path(quality_dataset)
    ledger = Path(checksum_ledger) if checksum_ledger is not None else evidence_root / "SHA256SUMS"
    if expected_ledger_sha256 is not None:
        observed_ledger_sha256 = hashlib.sha256(ledger.read_bytes()).hexdigest()
        if observed_ledger_sha256 != expected_ledger_sha256:
            raise ValueError("raw quality checksum ledger differs from its release lock")

    ledger_paths = checksum_ledger_paths(ledger, source_prefix=source_prefix)
    required_paths = {
        (_QUALITY_BATCH / raw_filename).as_posix()
        for _, raw_filename, _ in _LANES.values()
    }
    if expected_experiment_id is not None:
        required_paths.update({
            "experiment.json", "capacity/artifact-identities.json",
            "runtime-lock.json",
        })
    missing_bindings = sorted(required_paths - set(ledger_paths))
    if missing_bindings:
        raise ValueError(f"quality evidence is not checksum-bound: {missing_bindings}")
    checksum_result = verify_checksum_ledger(ledger, evidence_root, source_prefix=source_prefix)
    if not checksum_result.passed:
        raise ValueError(
            "quality evidence checksum verification failed: "
            f"missing={list(checksum_result.missing)}, "
            f"mismatched={list(checksum_result.mismatched)}"
        )
    if expected_experiment_id is not None:
        experiment = _load_json(evidence_root / "experiment.json")
        identities = _load_json(evidence_root / "capacity/artifact-identities.json")
        runtime_sha256 = hashlib.sha256(
            (evidence_root / "runtime-lock.json").read_bytes()
        ).hexdigest()
        if (
            experiment.get("experiment_id") != expected_experiment_id
            or not isinstance(identities, dict)
            or identities.get("source", {}).get("sha256")
            != expected_artifact_sha256
            or runtime_sha256 != expected_runtime_sha256
        ):
            raise ValueError(
                "raw quality model, runtime, or experiment identity differs from release"
            )

    cases = load_quality_cases(quality_dataset)
    if len(cases) != _EXPECTED_ROWS:
        raise ValueError(
            f"quality dataset row count is {len(cases)}; expected {_EXPECTED_ROWS}"
        )
    case_ids = {case.request.request_id for case in cases}

    derived: dict[str, QualityResult] = {}
    row_counts: dict[str, int] = {}
    for lane, (backend, raw_filename, normalized_filename) in _LANES.items():
        samples = _load_samples(
            evidence_root / _QUALITY_BATCH / raw_filename,
            backend=backend,
            expected_rows=_EXPECTED_ROWS,
        )
        sample_ids = {sample.request_id for sample in samples}
        if sample_ids != case_ids:
            missing = sorted(case_ids - sample_ids)[:3]
            unexpected = sorted(sample_ids - case_ids)[:3]
            raise ValueError(
                f"{lane} raw sample IDs do not match the quality dataset: "
                f"missing={missing}, unexpected={unexpected}"
            )
        observed = evaluate_quality(cases, samples)
        stored = quality_from_dict(
            _load_json(evidence_root / _QUALITY_REANALYSIS / normalized_filename)
        )
        if observed != stored:
            raise ValueError(f"{lane} normalized quality result does not match raw samples")
        derived[lane] = observed
        row_counts[lane] = len(samples)

    comparison = compare_quality(derived["disabled"], derived["enabled"])
    return RawQualitySummary(
        checksummed_files=checksum_result.checked,
        dataset_rows=len(cases),
        disabled_rows=row_counts["disabled"],
        enabled_rows=row_counts["enabled"],
        disabled_quality=derived["disabled"],
        enabled_quality=derived["enabled"],
        comparison=comparison,
    )
