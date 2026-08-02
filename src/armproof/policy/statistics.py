"""Deterministic statistics for repeated performance comparisons."""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class RatioEstimate:
    ratio: float
    lower_95: float
    upper_95: float
    baseline_median: float
    treatment_median: float
    baseline_samples: int
    treatment_samples: int


@dataclass(frozen=True)
class CapacityBracket:
    """Identifiable capacity ratio interval from confirmed pass/fail rates."""

    tested_ratio: float
    lower_bound: float
    upper_bound: float
    baseline_pass: float
    baseline_fail: float
    treatment_pass: float
    treatment_fail: float
    samples_per_boundary: int
    method: str = "confirmed-grid-bracket"


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def estimate_ratio(
    treatment: Sequence[float],
    baseline: Sequence[float],
    *,
    iterations: int = 10_000,
    seed: int = 0,
) -> RatioEstimate:
    """Estimate median treatment/baseline ratio with a percentile bootstrap CI."""
    if len(treatment) < 3 or len(baseline) < 3:
        raise ValueError("ratio estimates require at least three samples per treatment")
    if iterations < 100:
        raise ValueError("bootstrap requires at least 100 iterations")
    if any(not math.isfinite(value) or value <= 0 for value in (*treatment, *baseline)):
        raise ValueError("ratio samples must be finite and positive")
    treatment_median = statistics.median(treatment)
    baseline_median = statistics.median(baseline)
    rng = random.Random(seed)
    ratios = []
    for _ in range(iterations):
        sampled_treatment = [rng.choice(treatment) for _ in treatment]
        sampled_baseline = [rng.choice(baseline) for _ in baseline]
        ratios.append(statistics.median(sampled_treatment) / statistics.median(sampled_baseline))
    return RatioEstimate(
        ratio=treatment_median / baseline_median,
        lower_95=_quantile(ratios, 0.025),
        upper_95=_quantile(ratios, 0.975),
        baseline_median=baseline_median,
        treatment_median=treatment_median,
        baseline_samples=len(baseline),
        treatment_samples=len(treatment),
    )


def estimate_capacity_bracket(
    baseline_pass: Sequence[float],
    baseline_fail: Sequence[float],
    treatment_pass: Sequence[float],
    treatment_fail: Sequence[float],
) -> CapacityBracket:
    """Bound the unknown capacity ratio without treating grid points as samples."""
    groups = (baseline_pass, baseline_fail, treatment_pass, treatment_fail)
    lengths = {len(group) for group in groups}
    if len(lengths) != 1 or next(iter(lengths), 0) < 3:
        raise ValueError("capacity brackets require equal groups of at least three samples")
    if any(
        not math.isfinite(value) or value <= 0
        for group in groups
        for value in group
    ):
        raise ValueError("capacity boundary samples must be finite and positive")

    base_pass = statistics.median(baseline_pass)
    base_fail = statistics.median(baseline_fail)
    treat_pass = statistics.median(treatment_pass)
    treat_fail = statistics.median(treatment_fail)
    if base_pass >= base_fail or treat_pass >= treat_fail:
        raise ValueError("capacity pass/fail boundaries must be ordered")

    return CapacityBracket(
        tested_ratio=treat_pass / base_pass,
        lower_bound=treat_pass / base_fail,
        upper_bound=treat_fail / base_pass,
        baseline_pass=base_pass,
        baseline_fail=base_fail,
        treatment_pass=treat_pass,
        treatment_fail=treat_fail,
        samples_per_boundary=len(baseline_pass),
    )
