from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from armproof.evidence import verify_checksum_ledger


class ChecksumLedgerTests(unittest.TestCase):
    def test_verifies_relocated_guest_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "capacity" / "summary.json"
            artifact.parent.mkdir()
            artifact.write_text("accepted\n", encoding="utf-8")
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            ledger = root / "SHA256SUMS"
            ledger.write_text(
                f"{digest}  /opt/armproof/evidence/capacity/summary.json\n",
                encoding="utf-8",
            )
            result = verify_checksum_ledger(ledger, root)
            self.assertTrue(result.passed)
            self.assertEqual(result.checked, 1)

    def test_reports_mismatch_without_accepting_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "result.json"
            artifact.write_text("changed", encoding="utf-8")
            ledger = root / "SHA256SUMS"
            ledger.write_text(
                f"{'0' * 64}  /opt/armproof/evidence/result.json\n",
                encoding="utf-8",
            )
            result = verify_checksum_ledger(ledger, root)
            self.assertFalse(result.passed)
            self.assertEqual(result.mismatched, ("result.json",))

    def test_rejects_path_outside_frozen_guest_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = root / "SHA256SUMS"
            ledger.write_text(
                f"{'0' * 64}  /etc/passwd\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "outside source prefix"):
                verify_checksum_ledger(ledger, root)

    def test_empty_ledger_cannot_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = root / "SHA256SUMS"
            ledger.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "empty"):
                verify_checksum_ledger(ledger, root)


if __name__ == "__main__":
    unittest.main()
