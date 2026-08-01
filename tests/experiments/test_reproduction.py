from __future__ import annotations

import unittest

from armproof.experiments import compare_reproduction


def summary(short: float, long: float, mixed: float, *, passed: bool = True) -> dict:
    return {
        "passed": passed,
        "mixes": {
            "short": {"ratio": {"ratio": short}},
            "long": {"ratio": {"ratio": long}},
            "mixed": {"ratio": {"ratio": mixed}},
        },
    }


class ReproductionTests(unittest.TestCase):
    def test_all_mixes_within_ten_percent_pass(self) -> None:
        result = compare_reproduction(
            summary(3.0, 2.5, 3.0), summary(3.0, 2.4, 2.8)
        )
        self.assertTrue(result["passed"])
        self.assertTrue(result["mixes"]["mixed"]["within_tolerance"])

    def test_one_outlying_mix_fails(self) -> None:
        result = compare_reproduction(
            summary(3.0, 2.5, 3.0), summary(3.0, 2.0, 3.0)
        )
        self.assertFalse(result["passed"])
        self.assertFalse(result["mixes"]["long"]["within_tolerance"])

    def test_failed_reproduction_gate_cannot_pass(self) -> None:
        result = compare_reproduction(
            summary(3.0, 2.5, 3.0), summary(3.0, 2.5, 3.0, passed=False)
        )
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
