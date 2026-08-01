"""Dependency-free HTTP load primitives with request-level evidence."""

from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class RequestInput:
    request_id: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class RequestSample:
    request_id: str
    scheduled_ns: int
    started_ns: int
    finished_ns: int
    status_code: int | None
    error: str | None
    response: Mapping[str, Any] | None

    @property
    def latency_ms(self) -> float:
        return (self.finished_ns - self.started_ns) / 1_000_000

    @property
    def accepted(self) -> bool:
        return self.error is None and self.status_code is not None and 200 <= self.status_code < 300


@dataclass(frozen=True)
class LoadSummary:
    total: int
    accepted: int
    error_rate: float
    accepted_rps: float
    p50_ms: float | None
    p95_ms: float | None
    p99_ms: float | None


@dataclass(frozen=True)
class SloPolicy:
    p95_latency_ms: float
    max_error_rate: float
    minimum_delivery_ratio: float = 0.95

    def __post_init__(self) -> None:
        if self.p95_latency_ms <= 0:
            raise ValueError("p95_latency_ms must be positive")
        if not 0 <= self.max_error_rate <= 1:
            raise ValueError("max_error_rate must be between zero and one")
        if not 0 < self.minimum_delivery_ratio <= 1:
            raise ValueError("minimum_delivery_ratio must be in (0, 1]")


@dataclass(frozen=True)
class CapacityAttempt:
    target_rps: float
    summary: LoadSummary
    passed: bool


@dataclass(frozen=True)
class CapacityResult:
    sustainable_rps: float
    attempts: tuple[CapacityAttempt, ...]


Send = Callable[[RequestInput, int], RequestSample]


def _percentile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def summarize_samples(samples: Iterable[RequestSample], duration_seconds: float) -> LoadSummary:
    rows = tuple(samples)
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    accepted = [row for row in rows if row.accepted]
    latencies = [row.latency_ms for row in accepted]
    return LoadSummary(
        total=len(rows),
        accepted=len(accepted),
        error_rate=(len(rows) - len(accepted)) / len(rows) if rows else 1.0,
        accepted_rps=len(accepted) / duration_seconds,
        p50_ms=_percentile(latencies, 0.50),
        p95_ms=_percentile(latencies, 0.95),
        p99_ms=_percentile(latencies, 0.99),
    )


def send_http_json(url: str, request_input: RequestInput, scheduled_ns: int, timeout: float) -> RequestSample:
    started_ns = time.monotonic_ns()
    body = json.dumps(request_input.payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    status: int | None = None
    response_payload: Mapping[str, Any] | None = None
    error: str | None = None
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
            decoded = json.loads(response.read())
            if isinstance(decoded, dict):
                response_payload = decoded
            else:
                error = "response_not_object"
    except urllib.error.HTTPError as exc:
        status = exc.code
        error = "http_error"
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        error = type(exc).__name__
    return RequestSample(
        request_id=request_input.request_id,
        scheduled_ns=scheduled_ns,
        started_ns=started_ns,
        finished_ns=time.monotonic_ns(),
        status_code=status,
        error=error,
        response=response_payload,
    )


def run_closed_loop(
    requests: Sequence[RequestInput],
    send: Send,
    concurrency: int,
) -> list[RequestSample]:
    if concurrency < 1:
        raise ValueError("concurrency must be positive")
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(send, item, time.monotonic_ns()) for item in requests]
        return [future.result() for future in as_completed(futures)]


def run_open_loop(
    requests: Sequence[RequestInput],
    send: Send,
    target_rps: float,
    max_workers: int,
) -> list[RequestSample]:
    if target_rps <= 0 or max_workers < 1:
        raise ValueError("target_rps and max_workers must be positive")
    interval_ns = int(1_000_000_000 / target_rps)
    origin = time.monotonic_ns()
    futures = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for index, item in enumerate(requests):
            scheduled_ns = origin + index * interval_ns
            remaining_ns = scheduled_ns - time.monotonic_ns()
            if remaining_ns > 0:
                time.sleep(remaining_ns / 1_000_000_000)
            futures.append(executor.submit(send, item, scheduled_ns))
        return [future.result() for future in as_completed(futures)]


def find_sustainable_capacity(
    candidates_rps: Sequence[float],
    run_candidate: Callable[[float], list[RequestSample]],
    policy: SloPolicy,
    measurement_seconds: float,
) -> CapacityResult:
    if not candidates_rps:
        raise ValueError("capacity candidates cannot be empty")
    if sorted(candidates_rps) != list(candidates_rps) or len(set(candidates_rps)) != len(candidates_rps):
        raise ValueError("capacity candidates must be unique and ascending")
    attempts: list[CapacityAttempt] = []
    sustainable = 0.0
    for target_rps in candidates_rps:
        if target_rps <= 0:
            raise ValueError("capacity candidates must be positive")
        summary = summarize_samples(run_candidate(target_rps), measurement_seconds)
        passed = (
            summary.p95_ms is not None
            and summary.p95_ms <= policy.p95_latency_ms
            and summary.error_rate <= policy.max_error_rate
            and summary.accepted_rps >= target_rps * policy.minimum_delivery_ratio
        )
        attempts.append(CapacityAttempt(target_rps, summary, passed))
        if not passed:
            break
        sustainable = summary.accepted_rps
    return CapacityResult(sustainable, tuple(attempts))
