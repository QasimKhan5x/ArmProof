from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from armproof.evidence.identity import fingerprint_path


class ArtifactIdentityTests(unittest.TestCase):
    def test_directory_fingerprint_is_stable_and_content_sensitive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "nested").mkdir()
            (root / "a.txt").write_text("one")
            (root / "nested/b.txt").write_text("two")
            first = fingerprint_path(root)
            second = fingerprint_path(root)
            self.assertEqual(first, second)
            (root / "nested/b.txt").write_text("changed")
            self.assertNotEqual(first.sha256, fingerprint_path(root).sha256)

    def test_file_and_directory_have_distinct_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            item = root / "artifact"
            item.write_text("same bytes")
            file_identity = fingerprint_path(item)
            item.unlink()
            item.mkdir()
            (item / "payload").write_text("same bytes")
            self.assertNotEqual(file_identity.sha256, fingerprint_path(item).sha256)


if __name__ == "__main__":
    unittest.main()
