from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any, Callable

from armproof.evidence.raw_quality import verify_raw_quality_evidence


ROOT = Path(__file__).resolve().parents[2]
SOURCE_EVIDENCE = ROOT / "ops/evidence/EXP-2026-003/attempt-002/evidence"
QUALITY_DATASET = ROOT / "data/banking77/generated/quality.jsonl"
LANES = ("kleidiai-disabled", "kleidiai-enabled")


def _write_ledger(evidence: Path) -> None:
    relative_paths = [
        Path("capacity/quality-batch") / f"{lane}-samples.jsonl"
        for lane in LANES
    ] + [
        Path("capacity/quality-reanalysis") / f"{lane}.json"
        for lane in LANES
    ]
    lines = []
    for relative in relative_paths:
        digest = hashlib.sha256((evidence / relative).read_bytes()).hexdigest()
        lines.append(f"{digest}  /opt/armproof/evidence/{relative.as_posix()}")
    (evidence / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _copy_quality_evidence(destination: Path) -> Path:
    evidence = destination / "evidence"
    for directory in ("quality-batch", "quality-reanalysis"):
        target = evidence / "capacity" / directory
        target.mkdir(parents=True)
        source = SOURCE_EVIDENCE / "capacity" / directory
        for lane in LANES:
            suffix = "-samples.jsonl" if directory == "quality-batch" else ".json"
            shutil.copyfile(source / f"{lane}{suffix}", target / f"{lane}{suffix}")
    _write_ledger(evidence)
    return evidence


def _mutate_first_sample(
    evidence: Path,
    lane: str,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    path = evidence / "capacity/quality-batch" / f"{lane}-samples.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    mutate(row)
    lines[0] = json.dumps(row, separators=(",", ":"), sort_keys=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _write_ledger(evidence)


class RawQualityEvidenceTests(unittest.TestCase):
    def test_real_exp003_raw_quality_evidence_succeeds(self) -> None:
        ledger_digest = hashlib.sha256(
            (SOURCE_EVIDENCE / "SHA256SUMS").read_bytes()
        ).hexdigest()
        summary = verify_raw_quality_evidence(
            SOURCE_EVIDENCE,
            QUALITY_DATASET,
            expected_ledger_sha256=ledger_digest,
            expected_experiment_id="EXP-2026-003",
            expected_artifact_sha256=(
                "9ef697ababdc0b4ffc63b098bbd4760f79795eb0502ca4d41c80e20843ac0ab1"
            ),
            expected_runtime_sha256=(
                "68a4aa0e9b52bfacd435b1515aa5cc34acb760ba63961ddf70f6b0b01c96a884"
            ),
        )

        self.assertEqual(summary.checksummed_files, 111)
        self.assertEqual(summary.dataset_rows, 770)
        self.assertEqual(summary.disabled_rows, 770)
        self.assertEqual(summary.enabled_rows, 770)
        self.assertEqual(
            tuple(
                (
                    result.total,
                    result.correct,
                    result.schema_valid,
                    result.missing,
                    result.accuracy,
                    result.macro_f1,
                    result.schema_valid_rate,
                )
                for result in (summary.disabled_quality, summary.enabled_quality)
            ),
            (
                (770, 361, 770, 0, 0.4688311688311688, 0.41830617123053215, 1.0),
                (770, 358, 770, 0, 0.4649350649350649, 0.4115797269272764, 1.0),
            ),
        )

        with self.assertRaisesRegex(ValueError, "release lock"):
            verify_raw_quality_evidence(
                SOURCE_EVIDENCE,
                QUALITY_DATASET,
                expected_ledger_sha256="0" * 64,
            )
        with self.assertRaises(FrozenInstanceError):
            summary.dataset_rows = 0  # type: ignore[misc]

    def test_non_string_output_fails_after_checksum_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence = _copy_quality_evidence(Path(directory))

            def replace_output(row: dict[str, Any]) -> None:
                row["response"]["output"] = 17

            _mutate_first_sample(evidence, "kleidiai-enabled", replace_output)

            with self.assertRaisesRegex(ValueError, "output"):
                verify_raw_quality_evidence(evidence, QUALITY_DATASET)

    def test_string_output_tamper_fails_after_checksum_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence = _copy_quality_evidence(Path(directory))

            def replace_output(row: dict[str, Any]) -> None:
                row["response"]["output"] = '{"intent":"card_arrival"}'

            _mutate_first_sample(evidence, "kleidiai-enabled", replace_output)

            with self.assertRaisesRegex(ValueError, "normalized quality"):
                verify_raw_quality_evidence(evidence, QUALITY_DATASET)

    def test_wrong_backend_fails_after_checksum_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence = _copy_quality_evidence(Path(directory))

            def replace_backend(row: dict[str, Any]) -> None:
                row["response"]["backend"] = "kleidiai-disabled"

            _mutate_first_sample(evidence, "kleidiai-enabled", replace_backend)

            with self.assertRaisesRegex(ValueError, "backend"):
                verify_raw_quality_evidence(evidence, QUALITY_DATASET)

    def test_duplicate_sample_fails_after_checksum_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence = _copy_quality_evidence(Path(directory))
            path = (
                evidence
                / "capacity/quality-batch/kleidiai-enabled-samples.jsonl"
            )
            lines = path.read_text(encoding="utf-8").splitlines()
            lines[-1] = lines[0]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            _write_ledger(evidence)

            with self.assertRaisesRegex(ValueError, "duplicate"):
                verify_raw_quality_evidence(evidence, QUALITY_DATASET)


if __name__ == "__main__":
    unittest.main()
