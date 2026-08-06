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
        self.assertEqual(mixed["baseline_fail_rps"], 0.28)
        self.assertEqual(mixed["optimized_sustainable_rps"], 0.56)
        self.assertEqual(mixed["minimum_capacity_ratio"], 2.0)
        self.assertEqual(mixed["confirmation_seconds"], 500)
        self.assertEqual(mixed["confirmations_per_treatment"], 5)
        self.assertEqual(len(mixed["trial_matrix"]), 2)
        self.assertEqual(mixed["trial_matrix"][0]["outcomes"], ["fail"] * 5)
        self.assertEqual(mixed["trial_matrix"][1]["outcomes"], ["pass"] * 5)
        self.assertEqual(self.payload["provenance"]["experiment_id"], "EXP-2026-014")
        self.assertEqual(
            self.payload["provenance"]["release_experiment_id"], "EXP-2026-014"
        )
        self.assertEqual(
            self.payload["provenance"]["application_evaluation_experiment_id"],
            "EXP-2026-004",
        )
        self.assertIn(
            "Git object for EXP-2026-014 contains the exact final plan",
            self.payload["capacity"]["rate_selection"]["interpretation"],
        )
        self.assertIn(
            "10 windows of 500 seconds each",
            self.payload["capacity"]["rate_selection"]["interpretation"],
        )
        self.assertNotIn(
            "EXP-2026-012",
            self.payload["capacity"]["rate_selection"]["interpretation"],
        )

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

    def test_release_history_explains_the_rejected_identity_incomplete_run(self) -> None:
        history = self.payload["provenance"]["release_history"]
        self.assertEqual(history["rejected_experiment_id"], "EXP-2026-012")
        self.assertEqual(history["accepted_experiment_id"], "EXP-2026-014")
        self.assertIn("source_artifact_sha256", history["rejection_reason"])
        self.assertTrue(history["rates_unchanged"])

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
            "EXP-2026-014",
            "banking77-quality-0110",
            "[4, 5, 7]",
            "Five confirmations at every boundary",
            "all five within target",
            "all five missed target",
            "10-second p95 target",
            "ten seconds",
            "500-second trial",
        )
        for literal in forbidden:
            self.assertNotIn(literal, html)
            self.assertNotIn(literal, javascript)

    def test_reproduction_and_arm_attribution_are_explicit(self) -> None:
        proof = self.payload["proof"]
        self.assertEqual(proof["decision"], "PASS")
        self.assertEqual(
            proof["decision_source"],
            "derived_from_preregistered_confirmation",
        )
        self.assertEqual(
            proof["contract_id"], "phi4-graviton-kleidiai-confirmed-release"
        )
        self.assertEqual(proof["verified_claims"], 10)
        self.assertEqual(
            {row["id"] for row in proof["claims"]},
            {
                "quality-accuracy",
                "quality-macro-f1",
                "quality-schema",
                "sustained-capacity-lower-bound",
                "sustained-window-count",
                "sustained-request-count",
                "raw-quality-output-count",
                "arm-control-zero",
                "arm-treatment-share",
                "performix-sample-count",
            },
        )
        self.assertEqual(proof["reproduction_max_relative_difference_percent"], 0.0)
        self.assertTrue(proof["kleidiai_enabled_callchains"])
        self.assertFalse(proof["kleidiai_disabled_callchains"])
        self.assertGreater(proof["kleidiai_cycle_callchain_share_percent"], 50.0)
        self.assertEqual(proof["instance"], "c8g.4xlarge")
        performix = proof["performix"]
        self.assertEqual(performix["engine_version"], "1.20.0")
        self.assertEqual(performix["cpu"], "Neoverse-V2")
        self.assertEqual(performix["disabled_kai_sample_share_percent"], 0.0)
        self.assertEqual(performix["disabled_kai_function_samples"], 0)
        self.assertEqual(performix["disabled_function_samples"], 944847)
        self.assertEqual(performix["enabled_kai_function_samples"], 245876)
        self.assertEqual(performix["enabled_function_samples"], 365062)
        self.assertAlmostEqual(
            performix["enabled_kai_sample_share_percent"], 67.3518470835
        )
        self.assertIn("different denominator", performix["scope_note"])
        self.assertIn("neon_i8mm", performix["kernel_family"])

    def test_runtime_memory_recipe_is_derived_and_release_gated(self) -> None:
        memory = self.payload["proof"]["runtime_memory"]
        self.assertTrue(memory["passed"])
        self.assertEqual(memory["candidate_rps"], 0.62)
        self.assertEqual(memory["previous_capacity_rps"], 0.56)
        self.assertEqual(memory["confirmation_passes"], 5)
        self.assertEqual(memory["confirmation_windows"], 5)
        self.assertEqual(memory["simplification_failures"], 5)
        self.assertEqual(memory["simplification_windows"], 5)
        self.assertTrue(memory["outputs_equivalent"])
        self.assertEqual(memory["recipe"]["allocator"], "mimalloc")
        self.assertEqual(
            memory["recipe"]["transparent_huge_pages"], "always"
        )
        self.assertEqual(
            memory["recipe"]["onnxruntime_thread_overrides"],
            {
                "session.dynamic_block_base": "4",
                "session.intra_op.spin_backoff_max": "8",
                "session.intra_op.spin_duration_us": "1000",
            },
        )
        self.assertEqual(
            {row["id"] for row in self.payload["proof"]["runtime_release_conditions"]},
            {
                "paired-sustained-effect", "short-ablation",
                "simplification-rejected", "outputs-equivalent", "host-restored",
            },
        )
        self.assertEqual(
            [row["id"] for row in self.payload["optimization_journey"]["stages"]],
            ["model", "compute", "memory"],
        )

    def test_live_release_identity_is_fully_bound_to_the_audit(self) -> None:
        identity = self.payload["proof"]["live_deployment_identity"]
        self.assertEqual(identity["model_identity"], "d86ae7ca1f12b2ae4abe70abb856cb9c688908477a7de653467623764ab5c687")
        self.assertEqual(identity["runtime_lock_sha256"], "68a4aa0e9b52bfacd435b1515aa5cc34acb760ba63961ddf70f6b0b01c96a884")
        self.assertEqual(identity["instance_type"], "c8g.4xlarge")
        self.assertEqual(identity["cpu_affinity"], list(range(16)))
        self.assertEqual(identity["memory"]["baseline"]["allocator"], "system")
        self.assertEqual(identity["memory"]["optimized"]["allocator"], "mimalloc")
        self.assertEqual(
            identity["memory"]["optimized"]["transparent_huge_pages"], "always"
        )
        memory_recipe = self.payload["proof"]["runtime_memory"]["recipe"][
            "onnxruntime_thread_overrides"
        ]
        self.assertEqual(identity["runtime_tuning"]["optimized"], memory_recipe)
        self.assertTrue(memory_recipe)

    def test_demo_identifies_a_verified_matched_control_bundle(self) -> None:
        evidence = self.payload["provenance"]["evidence"]
        self.assertTrue(evidence["checksum_verified"])
        self.assertEqual(evidence["checksummed_files"], 141)
        self.assertTrue(evidence["reproduction_checksum_verified"])
        self.assertEqual(evidence["reproduction_checksummed_files"], 141)
        self.assertTrue(evidence["sustained_archive_verified"])
        self.assertTrue(evidence["sustained_internal_checksums_verified"])
        self.assertGreater(evidence["sustained_checksummed_files"], 40)
        self.assertGreater(evidence["raw_quality_checksummed_files"], 100)
        self.assertEqual(evidence["sustained_raw_confirmation_files"], 10)
        self.assertEqual(evidence["sustained_raw_confirmation_samples"], 2100)
        self.assertEqual(evidence["raw_quality_outputs"], 1540)
        self.assertTrue(evidence["sustained_matched_control_verified"])
        self.assertTrue(evidence["performix_archive_verified"])
        self.assertTrue(evidence["performix_internal_checksums_verified"])
        self.assertTrue(evidence["runtime_memory_archives_verified"])
        self.assertGreater(evidence["runtime_memory_checksummed_files"], 100)
        self.assertEqual(evidence["performix_checksummed_files"], 40)
        self.assertEqual(
            evidence["total_checksummed_files"],
            282
            + evidence["sustained_checksummed_files"]
            + evidence["raw_quality_checksummed_files"]
            + evidence["performix_checksummed_files"]
            + evidence["runtime_memory_checksummed_files"]
            + 4,
        )
        self.assertEqual(evidence["comparison"], "matched_control")
        self.assertEqual(evidence["only_changed_control"], "mlas.disable_kleidiai")


if __name__ == "__main__":
    unittest.main()
