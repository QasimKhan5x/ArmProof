from __future__ import annotations

import unittest
import csv
import io
import json
import tempfile
import zipfile
import hashlib
import math
import tarfile
from pathlib import Path

from armproof.evidence.performix import (
    compare_code_hotspots,
    extract_run_id,
    verify_performix_archive,
)


class PerformixOutputTests(unittest.TestCase):
    def test_extracts_run_id_from_streamed_progress(self) -> None:
        output = "\n".join(
            [
                '{"data":{"stage":"collect","progress":10,"run_id":{"value":"run-42"}}}',
                '{"data":{"stage":"complete","progress":100,"run_id":{"value":"run-42"}}}',
            ]
        )
        self.assertEqual(extract_run_id(output), "run-42")

    def test_extracts_string_run_id_from_wrapped_response(self) -> None:
        self.assertEqual(
            extract_run_id('{"code":"0","data":{"run_id":"run-7"}}'), "run-7"
        )

    def test_rejects_missing_or_conflicting_run_ids(self) -> None:
        with self.assertRaisesRegex(ValueError, "no run_id"):
            extract_run_id('{"data":{"stage":"prepare"}}')
        with self.assertRaisesRegex(ValueError, "conflicting"):
            extract_run_id('{"run_id":"one"}\n{"run_id":"two"}')


def _export(path: Path, run_id: str, treatment: str, rows: list[tuple[int, str]]) -> None:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Periodic Samples", "uid", "image", "symbol", "inlined from"])
    for index, (samples, symbol) in enumerate(rows):
        writer.writerow([samples, index, "libonnxruntime.so", symbol, ""])
    metadata = {
        "engine.version": "1.20.0",
        "run.recipe_name": "code_hotspots",
        "run.result": "success",
        "run.error": "",
        "run.workload.cmdline": f"python profile.py --model /variants/kleidiai-{treatment}",
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{run_id}/metadata.json", json.dumps(metadata))
        archive.writestr(
            f"{run_id}/tool/neoprof/0/output/functions-capture-periodic_sampling.csv",
            buffer.getvalue(),
        )
        archive.writestr(
            f"{run_id}/collector/sl-collect-target-info/sl-collect-target-info-cpus.json",
            json.dumps([{"name": "Neoverse-V2"}]),
        )


class PerformixExportTests(unittest.TestCase):
    def test_matched_positive_and_negative_exports_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _export(root / "disabled.zip", "disabled-run", "disabled", [(100, "Mlas")])
            _export(
                root / "enabled.zip", "enabled-run", "enabled",
                [(67, "kai_kernel_matmul_neon_i8mm"), (33, "Mlas")],
            )
            result = compare_code_hotspots(
                root / "disabled.zip", root / "enabled.zip",
                linux_perf_share=0.6853, maximum_share_difference=0.05,
            )
            self.assertTrue(result["passed"])
            self.assertAlmostEqual(result["enabled"]["kai_sample_share"], 0.67)

    def test_disabled_kai_samples_and_profiler_disagreement_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _export(root / "disabled.zip", "disabled-run", "disabled", [(1, "kai_bad")])
            _export(root / "enabled.zip", "enabled-run", "enabled", [(100, "kai_good")])
            with self.assertRaisesRegex(ValueError, "disabled"):
                compare_code_hotspots(
                    root / "disabled.zip", root / "enabled.zip",
                    linux_perf_share=0.6853, maximum_share_difference=0.05,
                )
            _export(root / "disabled.zip", "disabled-run", "disabled", [(100, "Mlas")])
            with self.assertRaisesRegex(ValueError, "contradicts"):
                compare_code_hotspots(
                    root / "disabled.zip", root / "enabled.zip",
                    linux_perf_share=0.1, maximum_share_difference=0.05,
                )
            with self.assertRaisesRegex(ValueError, "finite"):
                compare_code_hotspots(
                    root / "disabled.zip",
                    root / "enabled.zip",
                    linux_perf_share=math.nan,
                    maximum_share_difference=0.05,
                )

    def test_immutable_archive_is_verified_before_profiles_are_derived(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = root / "evidence"
            exports = evidence / "performix/exports"
            exports.mkdir(parents=True)
            _export(exports / "disabled.zip", "disabled", "disabled", [(100, "Mlas")])
            _export(
                exports / "enabled.zip",
                "enabled",
                "enabled",
                [(67, "kai_kernel_matmul_neon_i8mm"), (33, "Mlas")],
            )
            (evidence / "experiment.json").write_text(
                json.dumps({"experiment_id": "EXP-TEST"}), encoding="utf-8"
            )
            bound = [
                evidence / "experiment.json",
                exports / "disabled.zip",
                exports / "enabled.zip",
            ]
            (evidence / "SHA256SUMS").write_text(
                "".join(
                    f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
                    f"/opt/armproof/evidence/{path.relative_to(evidence).as_posix()}\n"
                    for path in bound
                ),
                encoding="utf-8",
            )
            archive_path = root / "evidence.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                archive.add(evidence, arcname="evidence")
            digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            result = verify_performix_archive(
                archive_path,
                expected_archive_sha256=digest,
                expected_experiment_id="EXP-TEST",
                disabled_run_id="disabled",
                enabled_run_id="enabled",
                linux_perf_share=0.6853,
                maximum_share_difference=0.05,
            )
            self.assertTrue(result["passed"])
            self.assertEqual(result["internal_checksums"]["checked"], 3)
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                verify_performix_archive(
                    archive_path,
                    expected_archive_sha256="0" * 64,
                    expected_experiment_id="EXP-TEST",
                    disabled_run_id="disabled",
                    enabled_run_id="enabled",
                    linux_perf_share=0.6853,
                    maximum_share_difference=0.05,
                )
