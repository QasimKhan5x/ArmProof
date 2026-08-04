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
        self.assertIn("PASS    9/9 claims from 4,200 raw request outcomes", rendered)
        self.assertIn("RELEASE at least 2.00x sustainable capacity", rendered)
        self.assertIn("BLOCK   altered archive refused before derivation", rendered)


if __name__ == "__main__":
    unittest.main()
