"""Preregistered fixed-SLO capacity experiment orchestration."""

from __future__ import annotations

import json
import platform
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from armproof.policy.statistics import estimate_capacity_bracket, estimate_ratio
from armproof.quality import (
    QualityResult,
    compare_quality,
    evaluate_quality,
    load_quality_cases,
    quality_to_dict,
)
from armproof.workload import (
    RequestInput,
    RequestSample,
    SloPolicy,
    load_requests_jsonl,
    materialize_requests,
    run_closed_loop,
    run_open_loop,
    summarize_samples,
    write_samples_jsonl,
)
from armproof.workload.load import send_http_json
from armproof.workload.io import summary_to_dict


@dataclass(frozen=True)
class TreatmentEndpoint:
    treatment_id: str
    endpoint: str


@dataclass(frozen=True)
class MixProtocol:
    mix_id: str
    workload: Path
    p95_slo_ms: float
    candidates_rps: tuple[float, ...]

    def __post_init__(self) -> None:
        if self.p95_slo_ms <= 0:
            raise ValueError("p95 SLO must be positive")
        if len(self.candidates_rps) < 2 or tuple(sorted(set(self.candidates_rps))) != self.candidates_rps:
            raise ValueError("candidate rates must be unique, ascending, and contain a failure bound")


@dataclass(frozen=True)
class FixedBoundary:
    mix_id: str
    treatment_id: str
    passing_rps: float
    failing_rps: float

    def __post_init__(self) -> None:
        if not self.mix_id or not self.treatment_id:
            raise ValueError("fixed boundary IDs must be non-empty")
        if self.passing_rps <= 0 or self.failing_rps <= self.passing_rps:
            raise ValueError("fixed boundary rates must be positive and ordered")


@dataclass(frozen=True)
class CapacityProtocol:
    experiment_id: str
    mixes: tuple[MixProtocol, ...]
    quality_dataset: Path
    discovery_seconds: float = 20.0
    confirmation_seconds: float = 30.0
    confirmations: int = 5
    max_error_rate: float = 0.01
    minimum_delivery_ratio: float = 0.95
    max_workers: int = 32
    request_timeout_seconds: float = 60.0
    warmup_requests: int = 3
    maximum_quality_loss_pp: float = 1.0
    minimum_schema_valid_rate: float = 0.99
    minimum_confirmation_requests: int = 1
    minimum_passing_mixes: int = 2
    minimum_tested_ratio: float = 1.5
    minimum_capacity_ratio_lower_bound: float = 1.15
    fixed_boundaries: tuple[FixedBoundary, ...] = ()

    def __post_init__(self) -> None:
        if not self.experiment_id.startswith("EXP-"):
            raise ValueError("experiment ID must start with EXP-")
        if not self.mixes or len({mix.mix_id for mix in self.mixes}) != len(self.mixes):
            raise ValueError("protocol requires distinct traffic mixes")
        if self.discovery_seconds <= 0 or self.confirmation_seconds <= 0:
            raise ValueError("measurement windows must be positive")
        if self.confirmations < 5:
            raise ValueError("at least five confirmations are required")
        if not 1 <= self.minimum_passing_mixes <= len(self.mixes):
            raise ValueError("minimum passing mixes must fit the configured traffic mixes")
        if self.minimum_confirmation_requests < 1:
            raise ValueError("minimum confirmation requests must be positive")
        for mix in self.mixes:
            minimum_rows = round(mix.candidates_rps[0] * self.confirmation_seconds)
            if minimum_rows < self.minimum_confirmation_requests:
                raise ValueError(
                    "confirmation window must contain at least "
                    f"{self.minimum_confirmation_requests} requests at the lowest candidate rate"
                )
        if self.fixed_boundaries:
            expected = {
                (mix.mix_id, treatment_id)
                for mix in self.mixes
                for treatment_id in ("kleidiai-disabled", "kleidiai-enabled")
            }
            observed = {
                (boundary.mix_id, boundary.treatment_id)
                for boundary in self.fixed_boundaries
            }
            if observed != expected or len(observed) != len(self.fixed_boundaries):
                raise ValueError("fixed boundaries must cover each mix and treatment exactly once")
        if self.maximum_quality_loss_pp < 0 or not 0 <= self.minimum_schema_valid_rate <= 1:
            raise ValueError("quality thresholds are invalid")


@dataclass(frozen=True)
class MinimumCapacityProtocol:
    """Confirm one conservative capacity lower bound without estimating a maximum."""

    experiment_id: str
    workload: Path
    quality_dataset: Path
    p95_slo_ms: float
    baseline_failing_rps: float
    treatment_passing_rps: float
    confirmation_seconds: float = 500.0
    confirmations: int = 5
    max_error_rate: float = 0.0
    minimum_delivery_ratio: float = 0.95
    max_workers: int = 48
    request_timeout_seconds: float = 60.0
    warmup_requests: int = 5
    maximum_quality_loss_pp: float = 1.0
    minimum_schema_valid_rate: float = 0.99
    minimum_confirmation_requests: int = 100
    minimum_capacity_ratio: float = 2.0

    def __post_init__(self) -> None:
        if not self.experiment_id.startswith("EXP-"):
            raise ValueError("experiment ID must start with EXP-")
        if self.p95_slo_ms <= 0 or self.confirmation_seconds <= 0:
            raise ValueError("SLO and confirmation duration must be positive")
        if self.confirmations < 5:
            raise ValueError("at least five confirmations are required")
        if self.baseline_failing_rps <= 0 or self.treatment_passing_rps <= 0:
            raise ValueError("confirmation rates must be positive")
        observed_ratio = self.treatment_passing_rps / self.baseline_failing_rps
        if observed_ratio < self.minimum_capacity_ratio:
            raise ValueError("frozen rates cannot establish the minimum capacity ratio")
        for rate in (self.baseline_failing_rps, self.treatment_passing_rps):
            if round(rate * self.confirmation_seconds) < self.minimum_confirmation_requests:
                raise ValueError("each confirmation must schedule enough requests")


SendRequest = Callable[[str, RequestInput, int, float], RequestSample]
PrepareWindow = Callable[[str, str], None]


def _default_send(endpoint: str, item: RequestInput, scheduled_ns: int, timeout: float) -> RequestSample:
    return send_http_json(endpoint, item, scheduled_ns, timeout)


def _run_window(
    endpoint: str,
    workload: Sequence[RequestInput],
    target_rps: float,
    seconds: float,
    max_workers: int,
    timeout: float,
    prefix: str,
    send: SendRequest,
) -> tuple[list[RequestSample], dict[str, Any], float]:
    count = max(1, round(target_rps * seconds))
    offered_rps = count / seconds
    requests = materialize_requests(workload, count, prefix)
    samples = run_open_loop(
        requests,
        lambda item, scheduled: send(endpoint, item, scheduled, timeout),
        target_rps=offered_rps,
        max_workers=max_workers,
    )
    summary = summarize_samples(samples, seconds)
    return samples, summary_to_dict(summary), offered_rps


def _passes(summary: Mapping[str, Any], target_rps: float, policy: SloPolicy) -> bool:
    p95 = summary["p95_ms"]
    return bool(
        p95 is not None
        and p95 <= policy.p95_latency_ms
        and summary["error_rate"] <= policy.max_error_rate
        and summary["accepted_rps"] >= target_rps * policy.minimum_delivery_ratio
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_capacity_experiment(
    protocol: CapacityProtocol,
    treatments: Sequence[TreatmentEndpoint],
    output: Path,
    *,
    send: SendRequest = _default_send,
    precomputed_quality: Mapping[str, QualityResult] | None = None,
    prepare_window: PrepareWindow | None = None,
) -> dict[str, Any]:
    if len(treatments) != 2 or len({item.treatment_id for item in treatments}) != 2:
        raise ValueError("exactly two distinct treatments are required")
    treatment_index = {item.treatment_id: item for item in treatments}
    if set(treatment_index) != {"kleidiai-disabled", "kleidiai-enabled"}:
        raise ValueError("treatments must be the matched KleidiAI enabled and disabled controls")
    output.mkdir(parents=True, exist_ok=True)
    started_at = time.time()
    _write_json(output / "protocol.json", {
        "experiment_id": protocol.experiment_id,
        "protocol": {
            **asdict(protocol),
            "mixes": [
                {**asdict(mix), "workload": str(mix.workload)} for mix in protocol.mixes
            ],
            "quality_dataset": str(protocol.quality_dataset),
        },
        "treatments": [asdict(item) for item in treatments],
    })
    _write_json(output / "environment.json", {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "processor": platform.processor(),
        "started_at_unix": started_at,
    })

    # Warm both processes before any accepted measurement.
    warm_base = load_requests_jsonl(protocol.mixes[0].workload)
    warm_requests = materialize_requests(warm_base, protocol.warmup_requests, "warmup")
    for treatment in treatments:
        samples = run_closed_loop(
            warm_requests,
            lambda item, scheduled, endpoint=treatment.endpoint: send(
                endpoint, item, scheduled, protocol.request_timeout_seconds
            ),
            concurrency=1,
        )
        write_samples_jsonl(output / "warmup" / f"{treatment.treatment_id}.jsonl", samples)
        if not all(sample.accepted for sample in samples):
            raise RuntimeError(f"warmup failed for {treatment.treatment_id}")

    # Identical-runtime quality is executed once per treatment on all frozen rows.
    quality_cases = load_quality_cases(protocol.quality_dataset)
    quality_results = dict(precomputed_quality or {})
    if quality_results and set(quality_results) != set(treatment_index):
        raise ValueError("precomputed quality must contain both matched treatments")
    if not quality_results:
        for treatment in treatments:
            samples = run_closed_loop(
                [case.request for case in quality_cases],
                lambda item, scheduled, endpoint=treatment.endpoint: send(
                    endpoint, item, scheduled, protocol.request_timeout_seconds
                ),
                concurrency=1,
            )
            write_samples_jsonl(output / "quality" / f"{treatment.treatment_id}-samples.jsonl", samples)
            quality_results[treatment.treatment_id] = evaluate_quality(quality_cases, samples)
    for treatment_id, result in quality_results.items():
        if result.total != len(quality_cases):
            raise ValueError(f"quality row count mismatch for {treatment_id}")
        _write_json(output / "quality" / f"{treatment_id}.json", quality_to_dict(result))
    comparison = compare_quality(
        quality_results["kleidiai-disabled"], quality_results["kleidiai-enabled"]
    )
    _write_json(output / "quality" / "comparison.json", asdict(comparison))

    def prepare(treatment_id: str, endpoint: str, window_id: str) -> None:
        if prepare_window is None:
            return
        prepare_window(treatment_id, window_id)
        requests = materialize_requests(
            warm_base, protocol.warmup_requests, f"window-warmup-{window_id}"
        )
        samples = run_closed_loop(
            requests,
            lambda item, scheduled: send(
                endpoint, item, scheduled, protocol.request_timeout_seconds
            ),
            concurrency=1,
        )
        write_samples_jsonl(output / "window-warmup" / f"{window_id}.jsonl", samples)
        if not all(sample.accepted for sample in samples):
            raise RuntimeError(f"window warmup failed for {window_id}")

    discovery: dict[str, dict[str, Any]] = {}
    boundaries: dict[str, dict[str, tuple[float, float]]] = {}
    for mix in protocol.mixes:
        base = load_requests_jsonl(mix.workload)
        policy = SloPolicy(mix.p95_slo_ms, protocol.max_error_rate, protocol.minimum_delivery_ratio)
        discovery[mix.mix_id] = {}
        boundaries[mix.mix_id] = {}
        for treatment_id in ("kleidiai-disabled", "kleidiai-enabled"):
            fixed = next((
                boundary for boundary in protocol.fixed_boundaries
                if boundary.mix_id == mix.mix_id
                and boundary.treatment_id == treatment_id
            ), None)
            if fixed is not None:
                boundaries[mix.mix_id][treatment_id] = (
                    fixed.passing_rps, fixed.failing_rps
                )
                discovery[mix.mix_id][treatment_id] = [{
                    "source": "preregistered_fixed_boundary",
                    "passing_rps": fixed.passing_rps,
                    "failing_rps": fixed.failing_rps,
                }]
                continue
            endpoint = treatment_index[treatment_id].endpoint
            attempts = []
            passing_rate: float | None = None
            failing_rate: float | None = None
            for index, target in enumerate(mix.candidates_rps):
                prefix = f"discovery-{mix.mix_id}-{treatment_id}-{target:g}"
                prepare(treatment_id, endpoint, prefix)
                samples, summary, offered_rps = _run_window(
                    endpoint, base, target, protocol.discovery_seconds,
                    protocol.max_workers, protocol.request_timeout_seconds, prefix, send,
                )
                passed = _passes(summary, offered_rps, policy)
                attempts.append({
                    "requested_rps": target,
                    "offered_rps": offered_rps,
                    "passed": passed,
                    "summary": summary,
                })
                write_samples_jsonl(
                    output / "capacity" / mix.mix_id / treatment_id / "discovery"
                    / f"rps-{target:g}.jsonl",
                    samples,
                )
                if passed:
                    passing_rate = target
                else:
                    failing_rate = target
                    break
            if passing_rate is None or failing_rate is None:
                raise RuntimeError(
                    f"discovery did not bracket capacity for {mix.mix_id}/{treatment_id}"
                )
            discovery[mix.mix_id][treatment_id] = attempts
            boundaries[mix.mix_id][treatment_id] = (passing_rate, failing_rate)

    # Counterbalance treatment order on each independent confirmation repetition.
    confirmations: dict[str, dict[str, list[dict[str, Any]]]] = {
        mix.mix_id: {item.treatment_id: [] for item in treatments} for mix in protocol.mixes
    }
    for repetition in range(protocol.confirmations):
        treatment_order = (
            ("kleidiai-disabled", "kleidiai-enabled")
            if repetition % 2 == 0 else ("kleidiai-enabled", "kleidiai-disabled")
        )
        for mix in protocol.mixes:
            base = load_requests_jsonl(mix.workload)
            policy = SloPolicy(mix.p95_slo_ms, protocol.max_error_rate, protocol.minimum_delivery_ratio)
            for treatment_id in treatment_order:
                passing_rate, failing_rate = boundaries[mix.mix_id][treatment_id]
                row: dict[str, Any] = {"repetition": repetition + 1}
                for boundary_name, target in (("pass", passing_rate), ("fail", failing_rate)):
                    prefix = f"confirm-{repetition + 1}-{mix.mix_id}-{treatment_id}-{boundary_name}"
                    prepare(
                        treatment_id, treatment_index[treatment_id].endpoint, prefix
                    )
                    samples, summary, offered_rps = _run_window(
                        treatment_index[treatment_id].endpoint, base, target,
                        protocol.confirmation_seconds, protocol.max_workers,
                        protocol.request_timeout_seconds, prefix, send,
                    )
                    observed_pass = _passes(summary, offered_rps, policy)
                    row[boundary_name] = {
                        "requested_rps": target,
                        "offered_rps": offered_rps,
                        "passed": observed_pass,
                        "summary": summary,
                    }
                    write_samples_jsonl(
                        output / "capacity" / mix.mix_id / treatment_id / "confirmations"
                        / f"rep-{repetition + 1}-{boundary_name}.jsonl",
                        samples,
                    )
                confirmations[mix.mix_id][treatment_id].append(row)

    mix_results = {}
    for mix in protocol.mixes:
        baseline_rows = confirmations[mix.mix_id]["kleidiai-disabled"]
        treatment_rows = confirmations[mix.mix_id]["kleidiai-enabled"]
        valid = all(row["pass"]["passed"] and not row["fail"]["passed"] for row in baseline_rows + treatment_rows)
        baseline_rates = [row["pass"]["summary"]["accepted_rps"] for row in baseline_rows]
        treatment_rates = [row["pass"]["summary"]["accepted_rps"] for row in treatment_rows]
        baseline_fail_rates = [row["fail"]["offered_rps"] for row in baseline_rows]
        treatment_fail_rates = [row["fail"]["offered_rps"] for row in treatment_rows]
        ratio = (
            estimate_ratio(treatment_rates, baseline_rates, seed=20260731)
            if valid else None
        )
        bracket = (
            estimate_capacity_bracket(
                baseline_rates,
                baseline_fail_rates,
                treatment_rates,
                treatment_fail_rates,
            )
            if valid else None
        )
        mix_results[mix.mix_id] = {
            "valid_boundary_confirmations": valid,
            "disabled_boundary": boundaries[mix.mix_id]["kleidiai-disabled"],
            "enabled_boundary": boundaries[mix.mix_id]["kleidiai-enabled"],
            "ratio": asdict(ratio) if ratio is not None else None,
            "capacity_bracket": asdict(bracket) if bracket is not None else None,
            "minimum_requests_per_confirmation": min(
                row[boundary]["summary"]["total"]
                for row in baseline_rows + treatment_rows
                for boundary in ("pass", "fail")
            ),
        }
    quality_passed = (
        comparison.accuracy_delta_pp >= -protocol.maximum_quality_loss_pp
        and comparison.macro_f1_delta_pp >= -protocol.maximum_quality_loss_pp
        and quality_results["kleidiai-disabled"].schema_valid_rate
        >= protocol.minimum_schema_valid_rate
        and quality_results["kleidiai-enabled"].schema_valid_rate
        >= protocol.minimum_schema_valid_rate
    )
    passing_mixes = sum(
        row["valid_boundary_confirmations"]
        and row["capacity_bracket"] is not None
        and row["capacity_bracket"]["tested_ratio"] >= protocol.minimum_tested_ratio
        and row["capacity_bracket"]["lower_bound"]
        >= protocol.minimum_capacity_ratio_lower_bound
        and row["minimum_requests_per_confirmation"]
        >= protocol.minimum_confirmation_requests
        for row in mix_results.values()
    )
    summary = {
        "schema_version": "1.0.0",
        "experiment_id": protocol.experiment_id,
        "quality_passed": quality_passed,
        "passing_mixes": passing_mixes,
        "passed": quality_passed and passing_mixes >= protocol.minimum_passing_mixes,
        "mixes": mix_results,
        "quality_comparison": asdict(comparison),
        "elapsed_seconds": time.time() - started_at,
    }
    _write_json(output / "discovery.json", discovery)
    _write_json(output / "confirmations.json", confirmations)
    _write_json(output / "summary.json", summary)
    return summary


def run_minimum_capacity_confirmation(
    protocol: MinimumCapacityProtocol,
    treatments: Sequence[TreatmentEndpoint],
    output: Path,
    *,
    send: SendRequest = _default_send,
    precomputed_quality: Mapping[str, QualityResult] | None = None,
    prepare_window: PrepareWindow | None = None,
) -> dict[str, Any]:
    """Confirm a preregistered lower bound using only its two identifying rates."""

    treatment_index = {item.treatment_id: item for item in treatments}
    if set(treatment_index) != {"kleidiai-disabled", "kleidiai-enabled"}:
        raise ValueError("treatments must be the matched KleidiAI enabled and disabled controls")
    output.mkdir(parents=True, exist_ok=True)
    started_at = time.time()
    _write_json(output / "protocol.json", {
        "experiment_id": protocol.experiment_id,
        "protocol": {**asdict(protocol), "workload": str(protocol.workload),
                     "quality_dataset": str(protocol.quality_dataset)},
        "treatments": [asdict(item) for item in treatments],
    })
    _write_json(output / "environment.json", {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "processor": platform.processor(),
        "started_at_unix": started_at,
    })

    workload = load_requests_jsonl(protocol.workload)
    warm_requests = materialize_requests(workload, protocol.warmup_requests, "warmup")
    for treatment in treatments:
        samples = run_closed_loop(
            warm_requests,
            lambda item, scheduled, endpoint=treatment.endpoint: send(
                endpoint, item, scheduled, protocol.request_timeout_seconds
            ),
            concurrency=1,
        )
        write_samples_jsonl(output / "warmup" / f"{treatment.treatment_id}.jsonl", samples)
        if not all(sample.accepted for sample in samples):
            raise RuntimeError(f"warmup failed for {treatment.treatment_id}")

    quality_cases = load_quality_cases(protocol.quality_dataset)
    quality_results = dict(precomputed_quality or {})
    if set(quality_results) != set(treatment_index):
        raise ValueError("precomputed quality must contain both matched treatments")
    for treatment_id, result in quality_results.items():
        if result.total != len(quality_cases):
            raise ValueError(f"quality row count mismatch for {treatment_id}")
        _write_json(output / "quality" / f"{treatment_id}.json", quality_to_dict(result))
    quality_comparison = compare_quality(
        quality_results["kleidiai-disabled"], quality_results["kleidiai-enabled"]
    )
    _write_json(output / "quality" / "comparison.json", asdict(quality_comparison))

    policy = SloPolicy(
        protocol.p95_slo_ms, protocol.max_error_rate, protocol.minimum_delivery_ratio
    )
    confirmations: list[dict[str, Any]] = []
    claim_rows = (
        ("kleidiai-disabled", protocol.baseline_failing_rps, False),
        ("kleidiai-enabled", protocol.treatment_passing_rps, True),
    )
    for repetition in range(protocol.confirmations):
        ordered = claim_rows if repetition % 2 == 0 else tuple(reversed(claim_rows))
        for treatment_id, requested_rps, expected_pass in ordered:
            window_id = f"confirm-{repetition + 1}-{treatment_id}"
            endpoint = treatment_index[treatment_id].endpoint
            if prepare_window is not None:
                prepare_window(treatment_id, window_id)
                window_warmup = materialize_requests(
                    workload, protocol.warmup_requests, f"window-warmup-{window_id}"
                )
                warm_samples = run_closed_loop(
                    window_warmup,
                    lambda item, scheduled: send(
                        endpoint, item, scheduled, protocol.request_timeout_seconds
                    ),
                    concurrency=1,
                )
                write_samples_jsonl(output / "window-warmup" / f"{window_id}.jsonl", warm_samples)
                if not all(sample.accepted for sample in warm_samples):
                    raise RuntimeError(f"window warmup failed for {window_id}")
            samples, sample_summary, offered_rps = _run_window(
                endpoint,
                workload,
                requested_rps,
                protocol.confirmation_seconds,
                protocol.max_workers,
                protocol.request_timeout_seconds,
                window_id,
                send,
            )
            observed_pass = _passes(sample_summary, offered_rps, policy)
            row = {
                "repetition": repetition + 1,
                "treatment_id": treatment_id,
                "requested_rps": requested_rps,
                "offered_rps": offered_rps,
                "expected_pass": expected_pass,
                "observed_pass": observed_pass,
                "matched_expectation": observed_pass is expected_pass,
                "summary": sample_summary,
            }
            confirmations.append(row)
            write_samples_jsonl(
                output / "confirmations" / f"{window_id}.jsonl", samples
            )

    quality_passed = (
        quality_comparison.accuracy_delta_pp >= -protocol.maximum_quality_loss_pp
        and quality_comparison.macro_f1_delta_pp >= -protocol.maximum_quality_loss_pp
        and all(
            result.schema_valid_rate >= protocol.minimum_schema_valid_rate
            for result in quality_results.values()
        )
    )
    boundary_passed = all(
        row["matched_expectation"]
        and row["summary"]["total"] >= protocol.minimum_confirmation_requests
        for row in confirmations
    )
    minimum_ratio = protocol.treatment_passing_rps / protocol.baseline_failing_rps
    summary = {
        "schema_version": "1.0.0",
        "experiment_id": protocol.experiment_id,
        "claim": "minimum_sustainable_capacity_ratio",
        "baseline_failing_rps": protocol.baseline_failing_rps,
        "treatment_passing_rps": protocol.treatment_passing_rps,
        "minimum_capacity_ratio": minimum_ratio,
        "confirmation_seconds": protocol.confirmation_seconds,
        "confirmation_count_per_treatment": protocol.confirmations,
        "raw_request_count": sum(row["summary"]["total"] for row in confirmations),
        "quality_passed": quality_passed,
        "boundary_passed": boundary_passed,
        "passed": quality_passed and boundary_passed
        and minimum_ratio >= protocol.minimum_capacity_ratio,
        "quality_comparison": asdict(quality_comparison),
        "confirmations": confirmations,
        "elapsed_seconds": time.time() - started_at,
    }
    _write_json(output / "confirmations.json", confirmations)
    _write_json(output / "summary.json", summary)
    return summary
