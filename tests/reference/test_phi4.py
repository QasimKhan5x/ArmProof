from __future__ import annotations

import json
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path

from armproof.reference.phi4 import _ort_model_identity, create_ort_variant, validate_request

ROOT = Path(__file__).resolve().parents[2]


class Phi4ReferenceTests(unittest.TestCase):
    def test_reference_imports_in_a_fresh_interpreter(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                (
                    "import sys; sys.path.insert(0, 'src'); "
                    "from armproof.reference import create_ort_variant; "
                    "assert callable(create_ort_variant)"
                ),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_matched_variants_change_only_session_control(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "model.onnx").write_bytes(b"model")
            (source / "genai_config.json").write_text(
                json.dumps({"model": {"decoder": {"session_options": {"existing": "same"}}}})
            )
            enabled = create_ort_variant(source, root / "enabled", True, 16)
            disabled = create_ort_variant(source, root / "disabled", False, 16)
            enabled_config = json.loads((enabled / "genai_config.json").read_text())
            disabled_config = json.loads((disabled / "genai_config.json").read_text())
            enabled_options = enabled_config["model"]["decoder"]["session_options"]
            disabled_options = disabled_config["model"]["decoder"]["session_options"]
            self.assertEqual(enabled_options["mlas.disable_kleidiai"], "0")
            self.assertEqual(disabled_options["mlas.disable_kleidiai"], "1")
            enabled_options.pop("mlas.disable_kleidiai")
            disabled_options.pop("mlas.disable_kleidiai")
            self.assertEqual(enabled_config, disabled_config)
            self.assertTrue((enabled / "model.onnx").is_symlink())
            enabled_identity, enabled_source, enabled_control, enabled_threads = _ort_model_identity(enabled)
            disabled_identity, disabled_source, disabled_control, disabled_threads = _ort_model_identity(disabled)
            self.assertEqual(enabled_identity, disabled_identity)
            self.assertEqual(enabled_source, disabled_source)
            self.assertEqual((enabled_control, disabled_control), ("0", "1"))
            self.assertEqual((enabled_threads, disabled_threads), (16, 16))
            (source / "model.onnx").write_bytes(b"changed-model")
            with self.assertRaisesRegex(ValueError, "no longer matches"):
                _ort_model_identity(enabled)

    def test_request_contract_is_bounded(self) -> None:
        self.assertEqual(validate_request({"request_id": "r", "prompt": "p"}), ("r", "p", 64))
        with self.assertRaisesRegex(ValueError, "between"):
            validate_request({"request_id": "r", "prompt": "p", "max_new_tokens": 0})
        with self.assertRaisesRegex(ValueError, "fields"):
            validate_request({"request_id": "r", "prompt": "p", "temperature": 1})


if __name__ == "__main__":
    unittest.main()
