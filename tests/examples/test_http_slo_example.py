from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from armproof.cli import main


ROOT = Path(__file__).resolve().parents[2]


class HttpSloExampleTests(unittest.TestCase):
    def test_generated_adoption_kit_passes_end_to_end(self) -> None:
        script = ROOT / "examples/http-slo/build_example.py"
        spec = importlib.util.spec_from_file_location("http_slo_example", script)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "kit"
            config = module.build(output)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["ci", str(config)]), 0)

            decision = json.loads(
                (output / "report/decision.json").read_text(encoding="utf-8")
            )
            self.assertTrue(decision["passed"])
            self.assertEqual(len(decision["claims"]), 5)
            self.assertTrue((output / ".github/workflows/armproof.yml").is_file())


if __name__ == "__main__":
    unittest.main()
