from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from armproof.reference.phi4 import create_ort_variant, validate_request


class Phi4ReferenceTests(unittest.TestCase):
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

    def test_request_contract_is_bounded(self) -> None:
        self.assertEqual(validate_request({"request_id": "r", "prompt": "p"}), ("r", "p", 64))
        with self.assertRaisesRegex(ValueError, "between"):
            validate_request({"request_id": "r", "prompt": "p", "max_new_tokens": 0})
        with self.assertRaisesRegex(ValueError, "fields"):
            validate_request({"request_id": "r", "prompt": "p", "temperature": 1})


if __name__ == "__main__":
    unittest.main()
