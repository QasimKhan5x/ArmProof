from __future__ import annotations

import unittest

from armproof.profiling import parse_perf_attribution


REPORT = """# Total Lost Samples: 0
# Samples: 31,000 of event 'cycles:P'
    68.68%     0.01%  python  libort.so  [.] kai_run_matmul_neon_i8mm
    59.94%    52.62%  python  libort.so  [.] label_opt_3
     0.88%     0.88%  python  libort.so  [.] kai_run_rhs_pack
"""


class PerfAttributionTests(unittest.TestCase):
    def test_uses_largest_inclusive_share_without_summing_nested_rows(self) -> None:
        result = parse_perf_attribution(REPORT, r"^kai_run_matmul")

        self.assertEqual(result.event, "cycles:P")
        self.assertEqual(result.samples, 31_000)
        self.assertEqual(result.lost_samples, 0)
        self.assertEqual(result.matching_rows, 1)
        self.assertAlmostEqual(result.maximum_children_share, 0.6868)
        self.assertEqual(result.maximum_children_symbol, "kai_run_matmul_neon_i8mm")

    def test_valid_control_with_no_matching_symbol_reports_zero(self) -> None:
        result = parse_perf_attribution(REPORT, r"^not_present")
        self.assertEqual(result.maximum_children_share, 0.0)
        self.assertIsNone(result.maximum_children_symbol)

    def test_missing_sample_metadata_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "sample metadata"):
            parse_perf_attribution("68.0% 1.0% command dso [.] kai_run", "kai")


if __name__ == "__main__":
    unittest.main()
