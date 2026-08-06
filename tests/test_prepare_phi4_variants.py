import tempfile
import unittest
from pathlib import Path

from scripts.prepare_phi4_variants import _clear_generated_variants


def _generated_overlay(root: Path, name: str) -> Path:
    overlay = root / name
    overlay.mkdir(parents=True)
    (overlay / "armproof_source_identity.json").write_text("{}\n", encoding="utf-8")
    return overlay


class PreparePhi4VariantsTests(unittest.TestCase):
    def test_clear_generated_variants_removes_only_verified_overlays(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _generated_overlay(root, "kleidiai-disabled")
            _generated_overlay(root, "kleidiai-enabled")

            _clear_generated_variants(root)

            self.assertEqual(list(root.iterdir()), [])

    def test_clear_generated_variants_rejects_unexpected_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _generated_overlay(root, "kleidiai-disabled")
            (root / "notes.txt").write_text("keep me\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "non-ArmProof content"):
                _clear_generated_variants(root)

            self.assertTrue((root / "notes.txt").is_file())
            self.assertTrue((root / "kleidiai-disabled").is_dir())

    def test_clear_generated_variants_rejects_unverified_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "kleidiai-enabled").mkdir()

            with self.assertRaisesRegex(ValueError, "unverified overlay"):
                _clear_generated_variants(root)

            self.assertTrue((root / "kleidiai-enabled").is_dir())
