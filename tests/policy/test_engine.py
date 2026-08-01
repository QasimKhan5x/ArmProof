from __future__ import annotations

import unittest

from armproof.domain import CausalScope, ClaimSpec, Comparison, TreatmentIdentity
from armproof.policy import evaluate_claims


def identity(enabled: bool, *, extra: str = "same") -> TreatmentIdentity:
    return TreatmentIdentity(
        treatment_id="enabled" if enabled else "disabled",
        artifact_sha256="a" * 64,
        runtime_sha256="b" * 64,
        workload_sha256="c" * 64,
        environment_sha256="d" * 64,
        controls={"kleidiai.enabled": enabled, "threads": 16, "extra": extra},
    )


def claim(**overrides: object) -> ClaimSpec:
    values = {
        "claim_id": "capacity",
        "causal_scope": CausalScope.ARM_ACCELERATION,
        "comparison_id": "on-off",
        "metric": "throughput_ratio",
        "operator": "gte",
        "threshold": 1.5,
        "required_evidence": frozenset({"request_samples", "arm_callchains"}),
        "required": True,
        "depends_on": (),
    }
    values.update(overrides)
    return ClaimSpec(**values)


def comparison(**overrides: object) -> Comparison:
    values = {
        "comparison_id": "on-off",
        "causal_scope": CausalScope.ARM_ACCELERATION,
        "baseline": identity(False),
        "treatment": identity(True),
        "metrics": {"throughput_ratio": 1.6},
        "evidence_kinds": frozenset({"request_samples", "arm_callchains"}),
        "arm_path_baseline_observed": False,
        "arm_path_treatment_observed": True,
    }
    values.update(overrides)
    return Comparison(**values)


class PolicyEngineTests(unittest.TestCase):
    def test_arm_capacity_claim_passes_with_matched_controls(self) -> None:
        decision = evaluate_claims([claim()], [comparison()])
        self.assertTrue(decision.passed)
        self.assertEqual(decision.claims[0].status.value, "pass")
        self.assertEqual(decision.claims[0].reason_code, "threshold_met")

    def test_missing_attribution_is_unknown_and_fails_contract(self) -> None:
        observed = comparison(arm_path_treatment_observed=None)
        decision = evaluate_claims([claim()], [observed])
        self.assertFalse(decision.passed)
        self.assertEqual(decision.claims[0].status.value, "unknown")
        self.assertEqual(decision.claims[0].reason_code, "attribution_missing")

    def test_uncontrolled_difference_invalidates_arm_claim(self) -> None:
        observed = comparison(treatment=identity(True, extra="changed"))
        decision = evaluate_claims([claim()], [observed])
        self.assertFalse(decision.passed)
        self.assertEqual(decision.claims[0].reason_code, "controls_mismatch")

    def test_failed_quality_dependency_blocks_performance_claim(self) -> None:
        quality = claim(
            claim_id="quality",
            causal_scope=CausalScope.WHOLE_DEPLOYMENT,
            comparison_id="quality",
            metric="quality_delta_pp",
            operator="gte",
            threshold=-1.0,
            required_evidence=frozenset({"quality_rows"}),
        )
        capacity = claim(depends_on=("quality",))
        quality_comparison = comparison(
            comparison_id="quality",
            causal_scope=CausalScope.WHOLE_DEPLOYMENT,
            metrics={"quality_delta_pp": -2.0},
            evidence_kinds=frozenset({"quality_rows"}),
            arm_path_baseline_observed=None,
            arm_path_treatment_observed=None,
        )
        decision = evaluate_claims([quality, capacity], [quality_comparison, comparison()])
        self.assertFalse(decision.passed)
        self.assertEqual(decision.claims[0].status.value, "fail")
        self.assertEqual(decision.claims[1].reason_code, "dependency_not_passed")

    def test_missing_metric_is_unknown(self) -> None:
        decision = evaluate_claims([claim()], [comparison(metrics={})])
        self.assertFalse(decision.passed)
        self.assertEqual(decision.claims[0].reason_code, "metric_missing")

    def test_dependencies_do_not_depend_on_declaration_order(self) -> None:
        quality = claim(
            claim_id="quality",
            causal_scope=CausalScope.WHOLE_DEPLOYMENT,
            comparison_id="quality",
            metric="quality_delta_pp",
            operator="gte",
            threshold=-1.0,
            required_evidence=frozenset({"quality_rows"}),
        )
        capacity = claim(depends_on=("quality",))
        quality_comparison = comparison(
            comparison_id="quality",
            causal_scope=CausalScope.WHOLE_DEPLOYMENT,
            metrics={"quality_delta_pp": 0.0},
            evidence_kinds=frozenset({"quality_rows"}),
            arm_path_baseline_observed=None,
            arm_path_treatment_observed=None,
        )
        decision = evaluate_claims([capacity, quality], [comparison(), quality_comparison])
        self.assertTrue(decision.passed)
        self.assertEqual([item.status.value for item in decision.claims], ["pass", "pass"])

    def test_duplicate_comparison_id_fails_closed(self) -> None:
        decision = evaluate_claims([claim()], [comparison(), comparison()])
        self.assertFalse(decision.passed)
        self.assertEqual(decision.claims[0].reason_code, "comparison_ambiguous")


if __name__ == "__main__":
    unittest.main()
