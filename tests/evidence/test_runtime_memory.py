from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from armproof.evidence.runtime_memory import (
    derive_runtime_memory_audit,
    verify_tuning_archive,
)


ROOT = Path(__file__).resolve().parents[2]


class RuntimeMemoryEvidenceTests(unittest.TestCase):
    def test_verifies_primary_tuning_archive_and_internal_ledger(self) -> None:
        path = ROOT / "ops/evidence/EXP-2026-015/evidence.tar.gz"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        archive = verify_tuning_archive(
            path,
            expected_sha256=digest,
            expected_experiment_id="EXP-2026-015",
        )
        self.assertEqual(archive.internal_checksummed_files, 63)
        self.assertEqual(archive.summary["winner"], "thread-memory")
        self.assertTrue(archive.summary["accepted"])
        self.assertEqual(archive.thp_before, archive.thp_after)

    def test_verifies_mechanism_isolation_archive(self) -> None:
        path = ROOT / "ops/evidence/EXP-2026-016/evidence.tar.gz"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        archive = verify_tuning_archive(
            path,
            expected_sha256=digest,
            expected_experiment_id="EXP-2026-016",
        )
        self.assertEqual(archive.internal_checksummed_files, 41)
        self.assertEqual(archive.summary["winner"], "mimalloc-thp")
        self.assertTrue(archive.summary["outputs_equivalent"])

    def test_rejects_wrong_archive_digest(self) -> None:
        path = ROOT / "ops/evidence/EXP-2026-016/evidence.tar.gz"
        with self.assertRaisesRegex(ValueError, "archive SHA-256 mismatch"):
            verify_tuning_archive(
                path,
                expected_sha256="0" * 64,
                expected_experiment_id="EXP-2026-016",
            )

    def test_derives_only_the_sustained_full_recipe(self) -> None:
        archives = []
        for experiment_id in ("EXP-2026-015", "EXP-2026-016", "EXP-2026-017"):
            path = ROOT / f"ops/evidence/{experiment_id}/evidence.tar.gz"
            archives.append(
                verify_tuning_archive(
                    path,
                    expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    expected_experiment_id=experiment_id,
                )
            )
        audit = derive_runtime_memory_audit(
            *archives,
            previous_capacity_rps=0.56,
            expected_output_digest=(
                "78b613260fabd3eefbfdbb030f8366ededfe3cd8d1003db85f70eeae5f48f684"
            ),
        )
        self.assertTrue(audit.passed)
        self.assertEqual(audit.confirmation_passes, 5)
        self.assertEqual(audit.simplification_failures, 5)
        self.assertEqual(audit.internal_checksummed_files, 130)
        self.assertEqual(audit.candidate_rps, 0.62)
        self.assertAlmostEqual(audit.capacity_gain_percent, 10.71428571428572)
        self.assertAlmostEqual(audit.baseline_median_p95_ms, 14806.349951)
        self.assertAlmostEqual(audit.optimized_median_p95_ms, 8146.752061)
        self.assertAlmostEqual(audit.simplification_median_p95_ms, 12287.705285)
        self.assertEqual(
            audit.recipe["onnxruntime_thread_overrides"],
            {
                "session.dynamic_block_base": "4",
                "session.intra_op.spin_backoff_max": "8",
                "session.intra_op.spin_duration_us": "1000",
            },
        )


if __name__ == "__main__":
    unittest.main()
