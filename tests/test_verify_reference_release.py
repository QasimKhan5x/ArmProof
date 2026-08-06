from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.verify_reference_release import verify_reference_release


class ReferenceReleaseVerificationTests(unittest.TestCase):
    def test_prints_the_verified_release_decision(self) -> None:
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

            with patch("scripts.verify_reference_release._run", side_effect=fake_run):
                with redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(
                        verify_reference_release(Path("armproof.json"), output_dir), 0
                    )
        rendered = output.getvalue()
        self.assertIn("PASS      10/10 required release claims", rendered)
        self.assertIn("CAPACITY  at least 2.00x", rendered)
        self.assertIn("EVIDENCE  2,100 capacity requests", rendered)
        self.assertIn("ARM PATH  67.00%", rendered)


if __name__ == "__main__":
    unittest.main()
