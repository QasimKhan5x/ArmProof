from __future__ import annotations

import json
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from armproof.cli import main


ROOT = Path(__file__).resolve().parents[1]


class CiCommandTests(unittest.TestCase):
    def test_reference_config_produces_decision_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report"
            with redirect_stdout(io.StringIO()):
                status = main([
                    "ci",
                    str(ROOT / "examples" / "armproof-reference" / "armproof.json"),
                    "--output", str(output),
                ])
            self.assertEqual(status, 0)
            self.assertTrue((output / "index.html").is_file())
            decision = json.loads((output / "decision.json").read_text(encoding="utf-8"))
            self.assertTrue(decision["passed"])
            self.assertTrue((output / "deployment-summary.json").is_file())

    def test_unknown_config_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "armproof.json"
            config.write_text(json.dumps({
                "schema_version": "1.0.0",
                "contract": "contract.json",
                "comparisons": ["comparison.json"],
                "summary": "summary.json",
                "surprise": True,
            }), encoding="utf-8")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["ci", str(config)]), 1)


if __name__ == "__main__":
    unittest.main()
