from __future__ import annotations

import hashlib
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from armproof.evidence.publication import verify_preregistration_publication


class PublicationEvidenceTests(unittest.TestCase):
    def test_plan_must_be_identical_in_project_and_measurement_archives(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = root / "EXP-TEST.json"
            plan.write_text('{"experiment_id":"EXP-TEST"}\n', encoding="utf-8")
            started = root / "started-at.txt"
            started.write_text("2026-08-04T23:00:00+00:00\n", encoding="utf-8")
            project = root / "project.tar.gz"
            with tarfile.open(project, "w:gz") as archive:
                archive.add(plan, arcname="ops/experiments/EXP-TEST.json")
            evidence = root / "evidence.tar.gz"
            with tarfile.open(evidence, "w:gz") as archive:
                archive.add(plan, arcname="evidence/experiment.json")
                archive.add(started, arcname="evidence/started-at.txt")
            record = root / "publication.json"
            record.write_text(json.dumps({
                "schema_version": "1.0.0",
                "experiment_id": "EXP-TEST",
                "preregistration_sha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
                "project_bundle_sha256": hashlib.sha256(project.read_bytes()).hexdigest(),
                "evidence_archive_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
                "git_commit": "a" * 40,
                "git_commit_time": "2026-08-04T22:59:00+00:00",
                "instance_launch_time": "2026-08-04T22:59:30+00:00",
                "public_commit_url": "https://github.com/example/repo/commit/" + "a" * 40,
            }), encoding="utf-8")
            result = verify_preregistration_publication(
                record,
                preregistration_path=plan,
                project_bundle_path=project,
                evidence_archive_path=evidence,
                expected_evidence_archive_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),
            )
            self.assertTrue(result["plan_embedded_in_measurement_archive"])

            changed = json.loads(plan.read_text(encoding="utf-8"))
            changed["claim"] = "changed later"
            plan.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest does not match"):
                verify_preregistration_publication(
                    record,
                    preregistration_path=plan,
                    project_bundle_path=project,
                    evidence_archive_path=evidence,
                    expected_evidence_archive_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),
                )


if __name__ == "__main__":
    unittest.main()
