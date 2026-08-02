from __future__ import annotations

import unittest
from pathlib import Path

from armproof.demo.surgedesk import build_surgedesk_payload


ROOT = Path(__file__).resolve().parents[2]


class SurgeDeskPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = build_surgedesk_payload(ROOT)

    def test_headline_capacity_comes_from_accepted_mixed_boundary(self) -> None:
        mixed = self.payload["capacity"]["mixes"]["mixed"]
        self.assertEqual(mixed["baseline_sustainable_rps"], 0.2)
        self.assertEqual(mixed["optimized_sustainable_rps"], 0.6)
        self.assertEqual(mixed["ratio"], 3.0)
        self.assertEqual(self.payload["provenance"]["experiment_id"], "EXP-2026-004")

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
        self.assertTrue(quality["human_confirmation_required"])

    def test_routes_are_recorded_outputs_with_both_correct_and_review_cases(self) -> None:
        cases = self.payload["routing_cases"]
        self.assertGreaterEqual(len(cases), 6)
        self.assertTrue(any(case["correct"] for case in cases))
        self.assertTrue(any(not case["correct"] for case in cases))
        self.assertTrue(any(case["guard_overrode"] for case in cases))
        self.assertTrue(all(case["mode"] == "recorded_model_output" for case in cases))
        self.assertTrue(all(case["source_text"] for case in cases))

    def test_replay_uses_raw_confirmation_samples(self) -> None:
        replay = self.payload["replay"]
        self.assertEqual(replay["baseline"]["offered_rps"], 0.26666666666666666)
        self.assertEqual(replay["optimized"]["offered_rps"], 0.26666666666666666)
        self.assertGreater(replay["baseline"]["p95_ms"], 10_000)
        self.assertLess(replay["optimized"]["p95_ms"], 10_000)
        self.assertEqual(len(replay["baseline"]["events"]), 8)
        self.assertEqual(len(replay["optimized"]["events"]), 8)
        self.assertTrue(all(event["latency_ms"] > 0 for event in replay["baseline"]["events"]))

    def test_reproduction_and_arm_attribution_are_explicit(self) -> None:
        proof = self.payload["proof"]
        self.assertEqual(proof["decision"], "PASS")
        self.assertEqual(proof["decision_source"], "derived_from_verified_evidence")
        self.assertEqual(proof["verified_claims"], 8)
        self.assertEqual(proof["reproduction_max_relative_difference_percent"], 0.0)
        self.assertTrue(proof["kleidiai_enabled_callchains"])
        self.assertFalse(proof["kleidiai_disabled_callchains"])
        self.assertGreater(proof["kleidiai_cycle_callchain_share_percent"], 50.0)
        self.assertEqual(proof["instance"], "c8g.4xlarge")

    def test_demo_identifies_a_verified_matched_control_bundle(self) -> None:
        evidence = self.payload["provenance"]["evidence"]
        self.assertTrue(evidence["checksum_verified"])
        self.assertEqual(evidence["checksummed_files"], 141)
        self.assertTrue(evidence["reproduction_checksum_verified"])
        self.assertEqual(evidence["reproduction_checksummed_files"], 141)
        self.assertEqual(evidence["total_checksummed_files"], 282)
        self.assertEqual(evidence["comparison"], "matched_control")
        self.assertEqual(evidence["only_changed_control"], "mlas.disable_kleidiai")


if __name__ == "__main__":
    unittest.main()
