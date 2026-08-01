"""Stable workload and request-evidence serialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Sequence

from armproof.workload.load import (
    CapacityResult,
    LoadSummary,
    RequestInput,
    RequestSample,
)


class WorkloadError(ValueError):
    """Frozen workload input is malformed."""


def load_requests_jsonl(path: Path) -> list[RequestInput]:
    requests = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise WorkloadError(f"invalid JSON on line {line_number}: {exc}") from exc
        if not isinstance(payload, dict) or set(payload) != {"request_id", "payload"}:
            raise WorkloadError(f"line {line_number} must contain request_id and payload")
        request_id = payload["request_id"]
        body = payload["payload"]
        if not isinstance(request_id, str) or not request_id or not isinstance(body, dict):
            raise WorkloadError(f"invalid request on line {line_number}")
        if request_id in seen:
            raise WorkloadError(f"duplicate request_id: {request_id}")
        seen.add(request_id)
        requests.append(RequestInput(request_id, body))
    if not requests:
        raise WorkloadError("workload contains no requests")
    return requests


def materialize_requests(base: Sequence[RequestInput], count: int, prefix: str) -> list[RequestInput]:
    if not base or count < 1:
        raise ValueError("base workload and count must be positive")
    return [
        RequestInput(f"{prefix}-{index:06d}-{base[index % len(base)].request_id}", base[index % len(base)].payload)
        for index in range(count)
    ]


def sample_to_dict(sample: RequestSample) -> dict[str, Any]:
    return {
        "request_id": sample.request_id,
        "scheduled_ns": sample.scheduled_ns,
        "started_ns": sample.started_ns,
        "finished_ns": sample.finished_ns,
        "latency_ms": sample.latency_ms,
        "status_code": sample.status_code,
        "error": sample.error,
        "response": sample.response,
    }


def write_samples_jsonl(path: Path, samples: Iterable[RequestSample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for sample in sorted(samples, key=lambda item: (item.scheduled_ns, item.request_id)):
            stream.write(json.dumps(sample_to_dict(sample), sort_keys=True, separators=(",", ":")) + "\n")


def summary_to_dict(summary: LoadSummary) -> dict[str, Any]:
    return {
        "total": summary.total,
        "accepted": summary.accepted,
        "error_rate": summary.error_rate,
        "accepted_rps": summary.accepted_rps,
        "p50_ms": summary.p50_ms,
        "p95_ms": summary.p95_ms,
        "p99_ms": summary.p99_ms,
    }


def capacity_to_dict(result: CapacityResult) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "sustainable_rps": result.sustainable_rps,
        "attempts": [
            {
                "target_rps": attempt.target_rps,
                "passed": attempt.passed,
                "summary": summary_to_dict(attempt.summary),
            }
            for attempt in result.attempts
        ],
    }
