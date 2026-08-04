from __future__ import annotations

import unittest
from pathlib import Path

from armproof.demo.surgedesk import build_surgedesk_payload


ROOT = Path(__file__).resolve().parents[2]


class SurgeDeskPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = build_surgedesk_payload(ROOT)

    def test_headline_capacity_comes_from_sustained_mixed_audit(self) -> None:
        mixed = self.payload["capacity"]["mixes"]["mixed"]
        self.assertEqual(mixed["baseline_sustainable_rps"], 0.24)
        self.assertEqual(mixed["baseline_fail_rps"], 0.28)
        self.assertEqual(mixed["optimized_sustainable_rps"], 0.56)
        self.assertAlmostEqual(mixed["tested_pass_point_ratio"], 2.3333333333)
        self.assertEqual(mixed["minimum_capacity_ratio"], 2.0)
        self.assertEqual(mixed["optimized_probe_passes"], 1)
        self.assertEqual(mixed["confirmation_seconds"], 500)
        self.assertEqual(len(mixed["trial_matrix"]), 4)
        self.assertEqual(
            mixed["trial_matrix"][3]["outcomes"],
            ["fail", "pass", "fail", "fail", "fail"],
        )
        self.assertEqual(self.payload["provenance"]["experiment_id"], "EXP-2026-009")
        self.assertFalse(self.payload["provenance"]["original_gate_passed"])
        self.assertTrue(self.payload["provenance"]["corrected_claim_passed"])

    def test_demo_exposes_absolute_quality_and_non_regression(self) -> None:
        quality = self.payload["quality"]
        self.assertAlmostEqual(quality["optimized_accuracy_percent"], 46.4935064935)
        self.assertAlmostEqual(quality["accuracy_delta_pp"], -0.3896103896)
        self.assertEqual(quality["schema_valid_percent"], 100.0)
        self.assertEqual(quality["llm_queue_correct"], 573)
        self.assertEqual(quality["guard_queue_correct"], 668)
        self.assertAlmostEqual(quality["guard_queue_accuracy_percent"], 86.7532467532)
        self.assertAlmostEqual(quality["guard_queue_gain_pp"], 12.3376623377)
        self.assertEqual(quality["guard_training_cases"], 2310)
        self.assertEqual(quality["guard_evaluation_cases"], 770)
        self.assertEqual(quality["intent_count"], 77)
        self.assertTrue(quality["human_confirmation_required"])

    def test_routes_are_recorded_outputs_with_both_correct_and_review_cases(self) -> None:
        cases = self.payload["routing_cases"]
        self.assertGreaterEqual(len(cases), 6)
        self.assertTrue(any(case["correct"] for case in cases))
        self.assertTrue(any(not case["correct"] for case in cases))
        self.assertTrue(any(case["guard_overrode"] for case in cases))
        self.assertTrue(all(case["mode"] == "recorded_model_output" for case in cases))
        self.assertTrue(all(case["source_text"] for case in cases))
        self.assertEqual(
            {case["scenario_role"] for case in cases if case["scenario_role"]},
            {"straight-through", "guard-intervention", "human-correction"},
        )

    def test_displayed_claim_boundary_is_the_conservative_formula(self) -> None:
        boundary = self.payload["provenance"]["claim_boundary"]
        self.assertEqual(boundary["released_lower_ratio"], 2.0)
        self.assertEqual(boundary["released_lower_formula"], "0.56 / 0.28")

    def test_static_ui_contains_no_embedded_experiment_results(self) -> None:
        html = (ROOT / "surgedesk/index.html").read_text(encoding="utf-8")
        javascript = (ROOT / "surgedesk/app.mjs").read_text(encoding="utf-8")
        forbidden = (
            "2.5×",
            "2.0×",
            "0.267 r/s",
            "0.600 r/s",
            "69-file",
            "282-file",
            "35-file",
            "EXP-2026-009",
            "banking77-quality-0110",
            "[4, 5, 7]",
            "Five confirmations at every boundary",
        )
        for literal in forbidden:
            self.assertNotIn(literal, html)
            self.assertNotIn(literal, javascript)

    def test_reproduction_and_arm_attribution_are_explicit(self) -> None:
        proof = self.payload["proof"]
        self.assertEqual(proof["decision"], "PASS")
        self.assertEqual(
            proof["decision_source"],
            "derived_from_versioned_sustained_contract",
        )
        self.assertEqual(
            proof["contract_id"], "phi4-graviton-kleidiai-sustained-release"
        )
        self.assertEqual(proof["verified_claims"], 9)
        self.assertEqual(
            {row["id"] for row in proof["claims"]},
            {
                "quality-accuracy",
                "quality-macro-f1",
                "quality-schema",
                "sustained-capacity-lower-bound",
                "sustained-window-count",
                "sustained-request-count",
                "arm-execution",
                "arm-cycle-attribution",
                "perf-sample-integrity",
            },
        )
        self.assertEqual(proof["reproduction_max_relative_difference_percent"], 0.0)
        self.assertTrue(proof["kleidiai_enabled_callchains"])
        self.assertFalse(proof["kleidiai_disabled_callchains"])
        self.assertAlmostEqual(proof["kleidiai_cycle_callchain_share_percent"], 68.53)
        self.assertEqual(proof["instance"], "c8g.4xlarge")
        performix = proof["performix"]
        self.assertEqual(performix["engine_version"], "1.20.0")
        self.assertEqual(performix["cpu"], "Neoverse-V2")
        self.assertEqual(performix["disabled_kai_sample_share_percent"], 0.0)
        self.assertAlmostEqual(
            performix["enabled_kai_sample_share_percent"], 67.0158291205
        )
        self.assertAlmostEqual(performix["absolute_share_difference_pp"], 1.5141708795)
        self.assertIn("neon_i8mm", performix["kernel_family"])

    def test_demo_identifies_a_verified_matched_control_bundle(self) -> None:
        evidence = self.payload["provenance"]["evidence"]
        self.assertTrue(evidence["checksum_verified"])
        self.assertEqual(evidence["checksummed_files"], 141)
        self.assertTrue(evidence["reproduction_checksum_verified"])
        self.assertEqual(evidence["reproduction_checksummed_files"], 141)
        self.assertTrue(evidence["sustained_archive_verified"])
        self.assertTrue(evidence["sustained_internal_checksums_verified"])
        self.assertEqual(evidence["sustained_checksummed_files"], 69)
        self.assertEqual(evidence["sustained_raw_confirmation_files"], 20)
        self.assertEqual(evidence["sustained_raw_confirmation_samples"], 4200)
        self.assertTrue(evidence["sustained_matched_control_verified"])
        self.assertTrue(evidence["performix_archive_verified"])
        self.assertTrue(evidence["performix_internal_checksums_verified"])
        self.assertGreater(evidence["performix_checksummed_files"], 20)
        self.assertEqual(
            evidence["total_checksummed_files"],
            351 + evidence["performix_checksummed_files"],
        )
        self.assertEqual(evidence["comparison"], "matched_control")
        self.assertEqual(evidence["only_changed_control"], "mlas.disable_kleidiai")


if __name__ == "__main__":
    unittest.main()
