from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.demo_release_gate import demonstrate


class DemoReleaseGateTests(unittest.TestCase):
    def test_prints_the_verified_release_decision_without_a_tamper_stunt(self) -> None:
        comparison = {
            "metrics": {
                "minimum_capacity_ratio": 2.0,
                "raw_confirmation_samples": 2100,
                "raw_quality_outputs": 1540,
                "performix_enabled_kai_share": 0.67,
            }
        }
        decision = {"claims": [{"id": str(index)} for index in range(10)]}
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)

            def fake_run(_config: Path, output: Path) -> tuple[int, str]:
                output.mkdir(parents=True, exist_ok=True)
                (output / "comparison.json").write_text(json.dumps(comparison))
                (output / "decision.json").write_text(json.dumps(decision))
                return 0, ""

            with patch("scripts.demo_release_gate._run", side_effect=fake_run):
                with redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(
                        demonstrate(Path("armproof.json"), output_dir), 0
                    )
        rendered = output.getvalue()
        self.assertIn("PASS      10/10 required release claims", rendered)
        self.assertIn("CAPACITY  at least 2.00x", rendered)
        self.assertIn("EVIDENCE  2,100 capacity requests", rendered)
        self.assertIn("ARM PATH  67.00%", rendered)
        self.assertNotIn("tamper", rendered.lower())
        self.assertNotIn("altered", rendered.lower())


if __name__ == "__main__":
    unittest.main()
