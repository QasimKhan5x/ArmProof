"""Pure policy evaluation over normalized comparison evidence."""

from __future__ import annotations

import math
from typing import Callable, Iterable

from armproof.domain import (
    CausalScope,
    ClaimResult,
    ClaimSpec,
    ClaimStatus,
    Comparison,
    Decision,
)


OPERATORS: dict[str, Callable[[float, float], bool]] = {
    "gte": lambda observed, threshold: observed >= threshold,
    "lte": lambda observed, threshold: observed <= threshold,
    "gt": lambda observed, threshold: observed > threshold,
    "lt": lambda observed, threshold: observed < threshold,
    "eq": lambda observed, threshold: observed == threshold,
}


def _result(
    claim: ClaimSpec,
    status: ClaimStatus,
    reason: str,
    observed: float | None = None,
) -> ClaimResult:
    return ClaimResult(claim.claim_id, status, reason, observed, claim.threshold)


def _arm_controls_match(comparison: Comparison) -> bool:
    baseline = comparison.baseline
    treatment = comparison.treatment
    identities_match = (
        baseline.artifact_sha256 == treatment.artifact_sha256
        and baseline.runtime_sha256 == treatment.runtime_sha256
        and baseline.workload_sha256 == treatment.workload_sha256
        and baseline.environment_sha256 == treatment.environment_sha256
    )
    baseline_controls = dict(baseline.controls)
    treatment_controls = dict(treatment.controls)
    control_keys = (
        "armproof.arm_acceleration_enabled",
        "kleidiai.enabled",
    )
    selected = [
        key for key in control_keys
        if key in baseline_controls or key in treatment_controls
    ]
    if len(selected) != 1:
        return False
    control = selected[0]
    baseline_enabled = baseline_controls.pop(control, None)
    treatment_enabled = treatment_controls.pop(control, None)
    return (
        identities_match
        and baseline_enabled in (False, "false", "0")
        and treatment_enabled in (True, "true", "1")
        and baseline_controls == treatment_controls
    )


def _evaluate_one(claim: ClaimSpec, comparison: Comparison | None) -> ClaimResult:
    if comparison is None:
        return _result(claim, ClaimStatus.UNKNOWN, "comparison_missing")
    if comparison.causal_scope is not claim.causal_scope:
        return _result(claim, ClaimStatus.UNKNOWN, "causal_scope_mismatch")
    missing = claim.required_evidence - comparison.evidence_kinds
    if missing:
        return _result(claim, ClaimStatus.UNKNOWN, "evidence_missing")
    if claim.causal_scope is CausalScope.ARM_ACCELERATION:
        if not _arm_controls_match(comparison):
            return _result(claim, ClaimStatus.UNKNOWN, "controls_mismatch")
        if (
            comparison.arm_path_baseline_observed is None
            or comparison.arm_path_treatment_observed is None
        ):
            return _result(claim, ClaimStatus.UNKNOWN, "attribution_missing")
        if comparison.arm_path_baseline_observed or not comparison.arm_path_treatment_observed:
            return _result(claim, ClaimStatus.FAIL, "attribution_control_failed")
    observed = comparison.metrics.get(claim.metric)
    if observed is None or not isinstance(observed, (int, float)) or not math.isfinite(observed):
        return _result(claim, ClaimStatus.UNKNOWN, "metric_missing")
    operator = OPERATORS.get(claim.operator)
    if operator is None:
        return _result(claim, ClaimStatus.UNKNOWN, "operator_unsupported", float(observed))
    passed = operator(float(observed), claim.threshold)
    return _result(
        claim,
        ClaimStatus.PASS if passed else ClaimStatus.FAIL,
        "threshold_met" if passed else "threshold_not_met",
        float(observed),
    )


def evaluate_claims(
    claims: Iterable[ClaimSpec],
    comparisons: Iterable[Comparison],
) -> Decision:
    specs = tuple(claims)
    comparison_groups: dict[str, list[Comparison]] = {}
    for comparison in comparisons:
        comparison_groups.setdefault(comparison.comparison_id, []).append(comparison)
    comparison_index = {
        comparison_id: rows[0]
        for comparison_id, rows in comparison_groups.items()
        if len(rows) == 1
    }
    ambiguous = {comparison_id for comparison_id, rows in comparison_groups.items() if len(rows) > 1}
    spec_index = {claim.claim_id: claim for claim in specs}
    result_index: dict[str, ClaimResult] = {}
    visiting: set[str] = set()

    def evaluate(claim: ClaimSpec) -> ClaimResult:
        if claim.claim_id in result_index:
            return result_index[claim.claim_id]
        if claim.claim_id in visiting:
            result = _result(claim, ClaimStatus.UNKNOWN, "dependency_cycle")
            result_index[claim.claim_id] = result
            return result
        visiting.add(claim.claim_id)
        dependencies = [
            evaluate(spec_index[dependency]) if dependency in spec_index else None
            for dependency in claim.depends_on
        ]
        if any(result is None or result.status is not ClaimStatus.PASS for result in dependencies):
            result = _result(claim, ClaimStatus.UNKNOWN, "dependency_not_passed")
        elif claim.comparison_id in ambiguous:
            result = _result(claim, ClaimStatus.UNKNOWN, "comparison_ambiguous")
        else:
            result = _evaluate_one(claim, comparison_index.get(claim.comparison_id))
        visiting.discard(claim.claim_id)
        result_index[claim.claim_id] = result
        return result

    results = [evaluate(claim) for claim in specs]
    required_ids = {claim.claim_id for claim in specs if claim.required}
    passed = all(
        result.status is ClaimStatus.PASS
        for result in results
        if result.claim_id in required_ids
    )
    return Decision(passed=passed, claims=tuple(results))
