from __future__ import annotations

import json
import hashlib
import shutil
import tarfile
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from armproof.contracts import parse_contract
from armproof.evidence.sustained_audit import derive_sustained_audit


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "examples/armproof-reference/sustained-contract.json"
CONTRACT = parse_contract(json.loads(CONTRACT_PATH.read_text()))


@contextmanager
def repacked_archive(
    mutate: Callable[[Path], None],
) -> Iterator[tuple[Path, str]]:
    source = ROOT / "ops/evidence/EXP-2026-009/evidence.tar.gz"
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        with tarfile.open(source, "r:gz") as archive:
            archive.extractall(root, filter="fully_trusted")
        evidence = root / "evidence"
        mutate(evidence)
        ledger = evidence / "SHA256SUMS"
        rewritten = []
        for line in ledger.read_text(encoding="utf-8").splitlines():
            _, original_path = line.split(maxsplit=1)
            relative = original_path.removeprefix("/opt/armproof/evidence/")
            digest = hashlib.sha256((evidence / relative).read_bytes()).hexdigest()
            rewritten.append(f"{digest}  {original_path}")
        ledger.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
        output = root / "repacked.tar.gz"
        with tarfile.open(output, "w:gz") as archive:
            archive.add(evidence, arcname="evidence", recursive=True)
        yield output, hashlib.sha256(output.read_bytes()).hexdigest()


class SustainedAuditTests(unittest.TestCase):
    def test_derives_only_the_conservative_exp009_claim(self) -> None:
        result = derive_sustained_audit(
            ROOT / "ops/evidence/EXP-2026-009/evidence.tar.gz",
            expected_sha256="f22e647aabe40eefd2abc5548306f40e2a5558ce1a85bc31c18319e6e51d78da",
            contract=CONTRACT,
            workload_manifest=ROOT / "data/banking77/generated/manifest.json",
        )

        self.assertEqual(result.experiment_id, "EXP-2026-009")
        self.assertFalse(result.original_gate_passed)
        self.assertTrue(result.corrected_claim_passed)
        self.assertEqual(result.baseline_pass_rps, 0.24)
        self.assertEqual(result.baseline_fail_rps, 0.28)
        self.assertEqual(result.treatment_pass_rps, 0.56)
        self.assertEqual(result.tested_pass_point_ratio, 0.56 / 0.24)
        self.assertEqual(result.minimum_capacity_ratio, 0.56 / 0.28)
        self.assertEqual(result.confirmations, 5)
        self.assertEqual(result.confirmation_seconds, 500)
        self.assertEqual(result.baseline_passes, 5)
        self.assertEqual(result.baseline_failures_at_fail_probe, 5)
        self.assertEqual(result.treatment_passes, 5)
        self.assertEqual(result.treatment_failures_at_fail_probe, 4)
        self.assertTrue(result.raw_samples_rederived)
        self.assertEqual(result.raw_confirmation_files, 20)
        self.assertEqual(result.raw_confirmation_samples, 4200)
        self.assertTrue(result.quality_passed)
        self.assertEqual(result.disabled_kai_cycle_share, 0.0)
        self.assertGreater(result.enabled_kai_cycle_share, 0.5)
        self.assertEqual(result.lost_perf_samples, 0)
        self.assertTrue(result.matched_control_verified)
        self.assertEqual(result.only_changed_control, "mlas.disable_kleidiai")
        self.assertTrue(result.internal_checksums_verified)
        self.assertEqual(result.internal_checksummed_files, 69)
        self.assertTrue(result.decision.passed)
        self.assertEqual(len(result.decision.claims), 9)

    def test_same_evidence_cannot_approve_the_rejected_exact_ratio(self) -> None:
        payload = json.loads(CONTRACT_PATH.read_text())
        claim = next(
            row
            for row in payload["claims"]
            if row["id"] == "sustained-capacity-lower-bound"
        )
        claim["threshold"] = 2.5
        strict_contract = parse_contract(payload)

        result = derive_sustained_audit(
            ROOT / "ops/evidence/EXP-2026-009/evidence.tar.gz",
            expected_sha256="f22e647aabe40eefd2abc5548306f40e2a5558ce1a85bc31c18319e6e51d78da",
            contract=strict_contract,
            workload_manifest=ROOT / "data/banking77/generated/manifest.json",
        )

        self.assertFalse(result.corrected_claim_passed)
        self.assertFalse(result.decision.passed)

    def test_contract_environment_must_match_observed_session_controls(self) -> None:
        payload = json.loads(CONTRACT_PATH.read_text())
        payload["treatments"][0]["environment"]["intra_op_num_threads"] = "8"
        with self.assertRaisesRegex(ValueError, "contract environment"):
            derive_sustained_audit(
                ROOT / "ops/evidence/EXP-2026-009/evidence.tar.gz",
                expected_sha256="f22e647aabe40eefd2abc5548306f40e2a5558ce1a85bc31c18319e6e51d78da",
                contract=parse_contract(payload),
                workload_manifest=ROOT / "data/banking77/generated/manifest.json",
            )

    def test_contract_command_must_be_the_complete_runnable_recipe(self) -> None:
        payload = json.loads(CONTRACT_PATH.read_text())
        payload["treatments"][1]["command"][-3] = "8"
        with self.assertRaisesRegex(ValueError, "contract command"):
            derive_sustained_audit(
                ROOT / "ops/evidence/EXP-2026-009/evidence.tar.gz",
                expected_sha256="f22e647aabe40eefd2abc5548306f40e2a5558ce1a85bc31c18319e6e51d78da",
                contract=parse_contract(payload),
                workload_manifest=ROOT / "data/banking77/generated/manifest.json",
            )

    def test_frozen_workload_content_must_match_its_manifest(self) -> None:
        source = ROOT / "data/banking77/generated"
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            for name in ("manifest.json", "quality.jsonl", "traffic-mixed.jsonl"):
                shutil.copyfile(source / name, destination / name)
            with (destination / "quality.jsonl").open("a", encoding="utf-8") as stream:
                stream.write("\n")
            with self.assertRaisesRegex(ValueError, "workload digest"):
                derive_sustained_audit(
                    ROOT / "ops/evidence/EXP-2026-009/evidence.tar.gz",
                    expected_sha256=(
                        "f22e647aabe40eefd2abc5548306f40e2a5558ce1a85bc31c18319e6e51d78da"
                    ),
                    contract=CONTRACT,
                    workload_manifest=destination / "manifest.json",
                )

    def test_repacked_boundary_substitution_fails_closed(self) -> None:
        def mutate(evidence: Path) -> None:
            protocol_path = evidence / "protocol.json"
            protocol = json.loads(protocol_path.read_text())
            protocol["fixed_boundaries"][0]["failing_rps"] = 0.27
            protocol_path.write_text(json.dumps(protocol), encoding="utf-8")

        with repacked_archive(mutate) as (archive, digest):
            with self.assertRaisesRegex(ValueError, "boundaries"):
                derive_sustained_audit(
                    archive,
                    expected_sha256=digest,
                    contract=CONTRACT,
                    workload_manifest=ROOT / "data/banking77/generated/manifest.json",
                )

    def test_repacked_backend_substitution_fails_closed(self) -> None:
        def mutate(evidence: Path) -> None:
            path = (
                evidence
                / "capacity/experiment/capacity/mixed/kleidiai-enabled/confirmations/rep-1-pass.jsonl"
            )
            lines = path.read_text(encoding="utf-8").splitlines()
            row = json.loads(lines[0])
            row["response"]["backend"] = "kleidiai-disabled"
            lines[0] = json.dumps(row, separators=(",", ":"))
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        with repacked_archive(mutate) as (archive, digest):
            with self.assertRaisesRegex(ValueError, "backend"):
                derive_sustained_audit(
                    archive,
                    expected_sha256=digest,
                    contract=CONTRACT,
                    workload_manifest=ROOT / "data/banking77/generated/manifest.json",
                )

    def test_repacked_schedule_compression_fails_closed(self) -> None:
        def mutate(evidence: Path) -> None:
            path = (
                evidence
                / "capacity/experiment/capacity/mixed/kleidiai-enabled/confirmations/rep-1-pass.jsonl"
            )
            lines = path.read_text(encoding="utf-8").splitlines()
            row = json.loads(lines[1])
            row["scheduled_ns"] -= 1_000_000_000
            lines[1] = json.dumps(row, separators=(",", ":"))
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        with repacked_archive(mutate) as (archive, digest):
            with self.assertRaisesRegex(ValueError, "cadence"):
                derive_sustained_audit(
                    archive,
                    expected_sha256=digest,
                    contract=CONTRACT,
                    workload_manifest=ROOT / "data/banking77/generated/manifest.json",
                )

    def test_repacked_quality_semantics_fail_closed(self) -> None:
        def mutate(evidence: Path) -> None:
            path = evidence / "capacity/experiment/quality/kleidiai-enabled.json"
            payload = json.loads(path.read_text())
            payload["rows"][0]["correct"] = not payload["rows"][0]["correct"]
            path.write_text(json.dumps(payload), encoding="utf-8")

        with repacked_archive(mutate) as (archive, digest):
            with self.assertRaisesRegex(ValueError, "row correctness"):
                derive_sustained_audit(
                    archive,
                    expected_sha256=digest,
                    contract=CONTRACT,
                    workload_manifest=ROOT / "data/banking77/generated/manifest.json",
                )

    def test_repacked_perf_event_substitution_fails_closed(self) -> None:
        def mutate(evidence: Path) -> None:
            path = evidence / "perf-enabled.txt"
            report = path.read_text(encoding="utf-8")
            path.write_text(report.replace("event 'cycles:P'", "event 'instructions'", 1))

        with repacked_archive(mutate) as (archive, digest):
            with self.assertRaisesRegex(ValueError, "sampled cycles"):
                derive_sustained_audit(
                    archive,
                    expected_sha256=digest,
                    contract=CONTRACT,
                    workload_manifest=ROOT / "data/banking77/generated/manifest.json",
                )

    def test_archive_tampering_fails_before_derivation(self) -> None:
        source = ROOT / "ops/evidence/EXP-2026-009/evidence.tar.gz"
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / "evidence.tar.gz"
            shutil.copyfile(source, changed)
            with changed.open("r+b") as stream:
                stream.seek(-1, 2)
                original = stream.read(1)[0]
                stream.seek(-1, 2)
                stream.write(bytes((original ^ 1,)))
            with self.assertRaisesRegex(ValueError, "digest"):
                derive_sustained_audit(
                    changed,
                    expected_sha256=(
                        "f22e647aabe40eefd2abc5548306f40e2a5558ce1a85bc31c18319e6e51d78da"
                    ),
                    contract=CONTRACT,
                    workload_manifest=ROOT / "data/banking77/generated/manifest.json",
                )


if __name__ == "__main__":
    unittest.main()
