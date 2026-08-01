from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from armproof.evidence.manifest import ManifestError, build_manifest, verify_manifest


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class ManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def valid_evidence(self) -> Path:
        evidence = self.root / "evidence"
        write_json(evidence / "EXP-2026-001" / "summary.json", {"passed": False})
        write_json(evidence / "EXP-2026-002" / "summary.json", {"passed": True})
        return evidence

    def archives(self) -> dict[str, Path]:
        source = self.root / "source"
        source.mkdir(exist_ok=True)
        archives = {}
        for experiment in ("EXP-2026-001", "EXP-2026-002"):
            archive = source / f"{experiment}.tar.gz"
            archive.write_bytes(experiment.encode())
            archives[experiment] = archive
        return archives

    def test_build_manifest_preserves_historical_decisions(self) -> None:
        evidence = self.valid_evidence()
        manifest = build_manifest(evidence, self.archives())

        self.assertEqual(
            manifest["experiments"],
            [
                {"experiment_id": "EXP-2026-001", "decision": "failed"},
                {"experiment_id": "EXP-2026-002", "decision": "passed"},
            ],
        )
        self.assertEqual(verify_manifest(evidence, manifest), [])

    def test_verify_manifest_reports_tampering(self) -> None:
        evidence = self.valid_evidence()
        manifest = build_manifest(evidence, self.archives())
        (evidence / "EXP-2026-002" / "summary.json").write_text("tampered")

        errors = verify_manifest(evidence, manifest)
        self.assertEqual(len(errors), 1)
        self.assertIn("mismatch", errors[0])

    def test_manifest_rejects_relabelled_first_experiment(self) -> None:
        evidence = self.valid_evidence()
        write_json(evidence / "EXP-2026-001" / "summary.json", {"passed": True})

        with self.assertRaisesRegex(ManifestError, "must remain failed"):
            build_manifest(evidence, {})

    def test_file_digest_matches_sha256(self) -> None:
        evidence = self.valid_evidence()
        payload = evidence / "EXP-2026-002" / "raw.json"
        payload.write_bytes(b"raw evidence")

        manifest = build_manifest(evidence, {})
        record = next(item for item in manifest["files"] if item["path"].endswith("raw.json"))
        self.assertEqual(record["sha256"], hashlib.sha256(b"raw evidence").hexdigest())


if __name__ == "__main__":
    unittest.main()
