from __future__ import annotations

import json
import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from armproof.cli import main


ROOT = Path(__file__).resolve().parents[2]


class CliFixtureTests(unittest.TestCase):
    def _evaluate(self, fixture: str) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "decision.json"
            root = ROOT / "examples" / fixture
            status = main([
                "verify",
                "--contract", str(root / "contract.json"),
                "--comparison", str(root / "comparison.json"),
                "--output", str(output),
            ])
            return status, json.loads(output.read_text(encoding="utf-8"))

    def test_pass_fixture_allows_release(self) -> None:
        status, decision = self._evaluate("fixture-pass")
        self.assertEqual(status, 0)
        self.assertTrue(decision["passed"])
        self.assertEqual(decision["claims"][0]["status"], "pass")

    def test_fail_fixture_blocks_measured_regression(self) -> None:
        status, decision = self._evaluate("fixture-fail")
        self.assertEqual(status, 2)
        self.assertFalse(decision["passed"])
        self.assertEqual(decision["claims"][0]["status"], "fail")
        self.assertEqual(decision["claims"][0]["reason_code"], "threshold_not_met")

    def test_unknown_fixture_blocks_missing_attribution(self) -> None:
        status, decision = self._evaluate("fixture-unknown")
        self.assertEqual(status, 2)
        self.assertFalse(decision["passed"])
        self.assertEqual(decision["claims"][0]["status"], "unknown")
        self.assertEqual(decision["claims"][0]["reason_code"], "attribution_missing")

    def test_normalized_verify_rejects_identities_not_declared_by_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            comparison = json.loads(
                (ROOT / "examples/fixture-pass/comparison.json").read_text(
                    encoding="utf-8"
                )
            )
            comparison["baseline"]["artifact_sha256"] = "f" * 64
            comparison["treatment"]["artifact_sha256"] = "f" * 64
            comparison_path = root / "comparison.json"
            comparison_path.write_text(json.dumps(comparison), encoding="utf-8")
            with redirect_stderr(io.StringIO()) as stderr:
                status = main(
                    [
                        "verify",
                        "--contract",
                        str(ROOT / "examples/fixture-pass/contract.json"),
                        "--comparison",
                        str(comparison_path),
                    ]
                )
            self.assertEqual(status, 1)
            self.assertIn("mismatched artifact_sha256", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
