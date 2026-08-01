from __future__ import annotations

import unittest

from armproof.collectors.memory import MemoryError, parse_smaps_rollup


class MemoryCollectorTests(unittest.TestCase):
    def test_parses_rss_and_pss_bytes(self) -> None:
        sample = parse_smaps_rollup("Rss: 1024 kB\nPss: 512 kB\nPrivate_Clean: 2 kB\n")
        self.assertEqual(sample.rss_bytes, 1024 * 1024)
        self.assertEqual(sample.pss_bytes, 512 * 1024)

    def test_missing_pss_is_rejected(self) -> None:
        with self.assertRaisesRegex(MemoryError, "RSS and PSS"):
            parse_smaps_rollup("Rss: 1024 kB\n")

    def test_unexpected_unit_is_rejected(self) -> None:
        with self.assertRaisesRegex(MemoryError, "unit"):
            parse_smaps_rollup("Rss: 1 MB\nPss: 1 MB\n")


if __name__ == "__main__":
    unittest.main()
