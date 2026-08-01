from __future__ import annotations

import unittest

from armproof.policy.statistics import estimate_ratio


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


if __name__ == "__main__":
    unittest.main()
