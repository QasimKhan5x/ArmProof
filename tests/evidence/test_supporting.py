from __future__ import annotations

import json
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from armproof.evidence.supporting import (
    derive_supporting_optimization,
    verified_deployment_summary,
)


ROOT = Path(__file__).resolve().parents[2]


class SupportingEvidenceTests(unittest.TestCase):
    def test_real_supporting_measurements_are_rederived(self) -> None:
        result = derive_supporting_optimization(
            ROOT / "ops/evidence/imported-migration-measurements/EXP-2026-002",
            ROOT / "examples/armproof-reference/supporting-evidence-lock.json",
        )
        self.assertEqual(len(result["direct_shape_gains"]), 4)
        self.assertGreater(min(result["direct_shape_gains"]), 1.7)
        self.assertGreater(result["disk_reduction_percent"], 35)
        self.assertGreater(result["peak_pss_reduction_percent"], 55)
        self.assertAlmostEqual(
            result["int4_peak_pss_reduction_percent"], 43.089459969982
        )
        self.assertEqual(
            result["migration_peak_pss_reduction_percent"],
            result["int4_peak_pss_reduction_percent"],
        )
        self.assertEqual(
            result["final_stack_peak_pss_reduction_percent"],
            result["peak_pss_reduction_percent"],
        )
        self.assertEqual(result["experiment_id"], "EXP-RESULT-FIRST-MEM-002")
        self.assertEqual(result["release_evidence_id"], "EXP-2026-002")
        self.assertEqual(
            result["pss_comparisons"]["migration_peak"]["treatment"],
            "INT4 with KleidiAI disabled",
        )
        self.assertEqual(
            result["pss_comparisons"]["final_stack_weighted"]["treatment"],
            "KleidiAI-enabled INT4 final stack",
        )

    def test_changed_summary_is_rejected_by_the_lock(self) -> None:
        source = ROOT / "examples/armproof-reference/supporting-evidence-lock.json"
        with tempfile.TemporaryDirectory() as directory:
            lock = json.loads(source.read_text(encoding="utf-8"))
            lock["files"]["summary.json"] = "0" * 64
            changed = Path(directory) / "lock.json"
            changed.write_text(json.dumps(lock), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                derive_supporting_optimization(
                    ROOT / "ops/evidence/imported-migration-measurements/EXP-2026-002", changed
                )

    def test_visible_deployment_metrics_must_match_rederived_evidence(self) -> None:
        summary = ROOT / "examples/armproof-reference/deployment-summary.json"
        verified, derived = verified_deployment_summary(
            summary,
            evidence_root=ROOT / "ops/evidence/imported-migration-measurements/EXP-2026-002",
            lock_path=ROOT / "examples/armproof-reference/supporting-evidence-lock.json",
        )
        self.assertEqual(
            verified["metrics"]["disk_reduction_percent"],
            derived["disk_reduction_percent"],
        )
        self.assertEqual(verified["metric_source"]["checksummed_files"], 4)
        self.assertEqual(
            verified["metric_source"]["source_experiment_id"],
            "EXP-RESULT-FIRST-MEM-002",
        )
        self.assertEqual(
            verified["metric_source"]["pss_evidence"],
            "locked_aggregate_statistics_no_raw_sample_trace",
        )
        self.assertEqual(
            verified["metric_scopes"]["final_stack_peak_pss_reduction_percent"],
            "KleidiAI-enabled INT4 final stack versus BF16",
        )
        self.assertNotIn("reproduction", verified)

        with tempfile.TemporaryDirectory() as directory:
            changed = json.loads(summary.read_text(encoding="utf-8"))
            changed["metrics"]["final_stack_peak_pss_reduction_percent"] = 99.0
            path = Path(directory) / "deployment.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "final_stack_peak_pss_reduction_percent"):
                verified_deployment_summary(
                    path,
                    evidence_root=ROOT / "ops/evidence/imported-migration-measurements/EXP-2026-002",
                    lock_path=ROOT / "examples/armproof-reference/supporting-evidence-lock.json",
                )

    def test_stored_median_cannot_hide_changed_raw_repetitions(self) -> None:
        source_root = ROOT / "ops/evidence/imported-migration-measurements/EXP-2026-002"
        source_lock = ROOT / "examples/armproof-reference/supporting-evidence-lock.json"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            root.mkdir()
            lock = json.loads(source_lock.read_text(encoding="utf-8"))
            for name in lock["files"]:
                shutil.copyfile(source_root / name, root / name)
            enabled = json.loads((root / "ort-enabled.json").read_text(encoding="utf-8"))
            for row in enabled["performance"][0]["rows"][:3]:
                row["end_to_end_seconds"] *= 3
            changed_path = root / "ort-enabled.json"
            changed_path.write_text(json.dumps(enabled), encoding="utf-8")
            lock["files"]["ort-enabled.json"] = hashlib.sha256(
                changed_path.read_bytes()
            ).hexdigest()
            lock_path = Path(directory) / "lock.json"
            lock_path.write_text(json.dumps(lock), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "stored median disagrees"):
                derive_supporting_optimization(root, lock_path)


if __name__ == "__main__":
    unittest.main()
