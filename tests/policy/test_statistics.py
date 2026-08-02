from __future__ import annotations

import unittest

from armproof.policy.statistics import estimate_capacity_bracket, estimate_ratio


class RatioStatisticsTests(unittest.TestCase):
    def test_seeded_bootstrap_is_deterministic(self) -> None:
        baseline = [10.0, 10.2, 9.8, 10.1, 9.9]
        treatment = [16.0, 16.2, 15.8, 16.1, 15.9]
        first = estimate_ratio(treatment, baseline, iterations=2000, seed=7)
        second = estimate_ratio(treatment, baseline, iterations=2000, seed=7)
        self.assertEqual(first, second)
        self.assertAlmostEqual(first.ratio, 1.6, places=2)
        self.assertGreater(first.lower_95, 1.5)

    def test_non_positive_or_too_few_samples_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "three"):
            estimate_ratio([2.0, 2.1], [1.0, 1.1])
        with self.assertRaisesRegex(ValueError, "positive"):
            estimate_ratio([2.0, 2.1, 2.2], [1.0, 0.0, 1.1])


class CapacityBracketTests(unittest.TestCase):
    def test_reports_tested_ratio_and_identifiable_capacity_interval(self) -> None:
        result = estimate_capacity_bracket(
            baseline_pass=[0.20] * 5,
            baseline_fail=[0.24] * 5,
            treatment_pass=[0.66] * 5,
            treatment_fail=[0.70] * 5,
        )

        self.assertAlmostEqual(result.tested_ratio, 3.3)
        self.assertAlmostEqual(result.lower_bound, 2.75)
        self.assertAlmostEqual(result.upper_bound, 3.5)
        self.assertEqual(result.method, "confirmed-grid-bracket")

    def test_rejects_unordered_boundaries(self) -> None:
        with self.assertRaisesRegex(ValueError, "ordered"):
            estimate_capacity_bracket(
                baseline_pass=[0.20] * 5,
                baseline_fail=[0.20] * 5,
                treatment_pass=[0.60] * 5,
                treatment_fail=[0.80] * 5,
            )


if __name__ == "__main__":
    unittest.main()
