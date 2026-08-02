from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from scripts.demo_release_gate import demonstrate


class DemoReleaseGateTests(unittest.TestCase):
    def test_valid_evidence_passes_and_tampered_ledger_blocks(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(demonstrate(), 0)
        rendered = output.getvalue()
        self.assertIn("PASS    8/8 claims from 282 verified files", rendered)
        self.assertIn("BLOCK   release refused", rendered)


if __name__ == "__main__":
    unittest.main()
