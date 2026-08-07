from __future__ import annotations

import hashlib
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

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
        self.assertEqual(audit.raw_output_cases, 186)
        self.assertEqual(audit.raw_output_rows, 2790)
        self.assertEqual(audit.complete_raw_windows, 31)
        self.assertEqual(audit.complete_raw_rows, 3678)
        self.assertEqual(audit.sustained_equivalence_rows, 2790)
        self.assertEqual(
            audit.recipe["evidence_counts"],
            {
                "complete_raw_windows": 31,
                "complete_raw_rows": 3678,
                "sustained_equivalence_cases": 186,
                "sustained_equivalence_rows": 2790,
            },
        )
        self.assertEqual(len(audit.raw_output_digest), 64)
        self.assertEqual(
            audit.recipe["observed_host_state"]["allocator"], None
        )
        self.assertEqual(
            audit.recipe["observed_host_state"]["allocator_evidence"],
            "not_observed_no_proc_maps_archived",
        )
        self.assertEqual(
            audit.recipe["setting_evidence"]["allocator"],
            "declared_variant_metadata_only",
        )
        self.assertEqual(
            audit.recipe["observed_host_state"]["transparent_huge_pages"],
            "always",
        )
        self.assertEqual(
            audit.recipe["onnxruntime_thread_overrides"],
            {
                "session.dynamic_block_base": "4",
                "session.intra_op.spin_backoff_max": "8",
                "session.intra_op.spin_duration_us": "1000",
            },
        )

    def test_stored_runtime_summary_cannot_override_raw_request_rows(self) -> None:
        archives = self._archives()
        changed_summary = dict(archives[0].summary)
        changed_rows = [dict(row) for row in changed_summary["rows"]]
        target = next(
            row
            for row in changed_rows
            if row["phase"] == "confirmation" and row["variant_id"] == "thread-memory"
        )
        target["summary"] = {**target["summary"], "p95_ms": 1.0}
        changed_summary["rows"] = changed_rows
        archives[0] = replace(
            archives[0], summary=MappingProxyType(changed_summary)
        )
        with self.assertRaisesRegex(ValueError, "per-window summary disagrees"):
            self._derive(archives)

    def test_sustained_screen_summary_cannot_override_raw_request_rows(self) -> None:
        archives = self._archives()
        changed_summary = dict(archives[0].summary)
        changed_rows = [dict(row) for row in changed_summary["rows"]]
        target = next(
            row
            for row in changed_rows
            if row["phase"] == "screen" and row["variant_id"] == "current"
        )
        target["summary"] = {**target["summary"], "p95_ms": 1.0}
        changed_summary["rows"] = changed_rows
        archives[0] = replace(
            archives[0], summary=MappingProxyType(changed_summary)
        )
        with self.assertRaisesRegex(ValueError, "per-window summary disagrees"):
            self._derive(archives)

    def test_per_window_summary_must_match_aggregate_summary(self) -> None:
        archives = self._archives()
        summaries = dict(archives[0].window_summaries)
        field = "evidence/tuning/screen/current/rep-1.summary.json"
        changed = dict(summaries[field])
        changed["passed"] = not changed["passed"]
        summaries[field] = MappingProxyType(changed)
        archives[0] = replace(
            archives[0], window_summaries=MappingProxyType(summaries)
        )
        with self.assertRaisesRegex(ValueError, "per-window summary disagrees"):
            self._derive(archives)

    def test_nonselected_raw_window_must_match_its_stored_summary(self) -> None:
        archives = self._archives()
        raw_windows = dict(archives[0].raw_windows)
        field = "evidence/tuning/screen/mimalloc/rep-1.jsonl"
        changed_rows = []
        for raw in raw_windows[field]:
            changed = dict(raw)
            changed["finished_ns"] += 1_000_000_000
            changed["latency_ms"] += 1000.0
            changed_rows.append(MappingProxyType(changed))
        raw_windows[field] = tuple(changed_rows)
        archives[0] = replace(
            archives[0], raw_windows=MappingProxyType(raw_windows)
        )
        with self.assertRaisesRegex(ValueError, "stored summary disagrees with raw rows"):
            self._derive(archives)

    def test_archived_variant_config_must_match_declared_session_options(self) -> None:
        archives = self._archives()
        configs = dict(archives[0].variant_configs)
        changed = deepcopy(dict(configs["thread-memory"]))
        changed["model"]["decoder"]["session_options"][
            "session.dynamic_block_base"
        ] = "99"
        configs["thread-memory"] = MappingProxyType(changed)
        archives[0] = replace(
            archives[0], variant_configs=MappingProxyType(configs)
        )
        with self.assertRaisesRegex(ValueError, "variant config"):
            self._derive(archives)

    @staticmethod
    def _archives() -> list[object]:
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
        return archives

    @staticmethod
    def _derive(archives: list[object]) -> object:
        return derive_runtime_memory_audit(
            *archives,
            previous_capacity_rps=0.56,
            expected_output_digest=(
                "78b613260fabd3eefbfdbb030f8366ededfe3cd8d1003db85f70eeae5f48f684"
            ),
        )


if __name__ == "__main__":
    unittest.main()
