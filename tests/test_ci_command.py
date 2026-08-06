from __future__ import annotations

import json
import io
import hashlib
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from armproof.cli import main


ROOT = Path(__file__).resolve().parents[1]


class CiCommandTests(unittest.TestCase):
    def test_init_scaffolds_a_fail_closed_http_adoption_kit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "kit"
            with redirect_stdout(io.StringIO()) as stdout:
                status = main([
                    "init",
                    "--endpoint", "http://127.0.0.1:8000/infer",
                    "--output", str(output),
                ])
            self.assertEqual(status, 0)
            self.assertIn("Next:", stdout.getvalue())
            expected = {
                "armproof.json",
                "contract.json",
                "collection-plan.json",
                "workload.jsonl",
                "quality.jsonl",
                "identity-sources/artifact.ref",
                "identity-sources/runtime.lock",
                "identity-sources/environment.json",
                "identity-sources/workload-manifest.json",
                "templates/protocol.json",
                "templates/identities.json",
                "templates/profile-manifest.json",
                "ADOPTION_CHECKLIST.md",
                "EVIDENCE_LAYOUT.md",
                "README.md",
                ".github/workflows/armproof.yml",
            }
            self.assertTrue(all((output / relative).is_file() for relative in expected))
            plan = json.loads(
                (output / "collection-plan.json").read_text(encoding="utf-8")
            )
            self.assertEqual(plan["endpoint"], "http://127.0.0.1:8000/infer")
            self.assertEqual(
                len(
                    plan["expected_evidence_layout"]["boundaries"]["baseline"][
                        "pass"
                    ]
                ),
                3,
            )
            self.assertEqual(
                plan["expected_evidence_layout"]["identity_sources"]["artifact"],
                "evidence/identity-sources/artifact.ref",
            )
            protocol_template = json.loads(
                (output / "templates/protocol.json").read_text(encoding="utf-8")
            )
            self.assertEqual(protocol_template["boundaries"], plan["expected_evidence_layout"]["boundaries"])
            identities_template = json.loads(
                (output / "templates/identities.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                identities_template["treatment"]["controls"]["armproof.arm_acceleration_enabled"],
                "true",
            )
            profile_template = json.loads(
                (output / "templates/profile-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(profile_template["profiler"], "linux-perf")
            self.assertEqual(set(profile_template["runs"]), {"baseline", "treatment"})
            config = json.loads((output / "armproof.json").read_text(encoding="utf-8"))
            self.assertEqual(config["evidence"]["adapter"], "http-slo-v1")
            workflow = (output / ".github/workflows/armproof.yml").read_text(
                encoding="utf-8"
            )
            self.assertIn(
                "QasimKhan5x/ArmProof@32c1ad339b2a09d66af73aa391ed311962e215c7 # v1.0.0",
                workflow,
            )
            self.assertIn("fetch-depth: 0", workflow)
            self.assertIn("Created 17 files", stdout.getvalue())

            tree_digest = hashlib.sha256()
            for path in sorted(item for item in output.rglob("*") if item.is_file()):
                tree_digest.update(path.relative_to(output).as_posix().encode("utf-8"))
                tree_digest.update(b"\0")
                tree_digest.update(path.read_bytes())
                tree_digest.update(b"\0")
            self.assertEqual(
                tree_digest.hexdigest(),
                "362c6e498b6a8e05175b507ed25e4ac8ab85c68ad696dcd2ca3029c65a24b578",
            )

            original_contract_digest = hashlib.sha256(
                (output / "contract.json").read_bytes()
            ).hexdigest()
            (output / "identity-sources/artifact.ref").write_text(
                "owner/model@new-revision\n", encoding="utf-8"
            )
            subprocess.run(
                [sys.executable, str(output / "refresh_bindings.py")],
                check=True,
                capture_output=True,
                text=True,
            )
            refreshed_contract_digest = hashlib.sha256(
                (output / "contract.json").read_bytes()
            ).hexdigest()
            self.assertNotEqual(original_contract_digest, refreshed_contract_digest)
            refreshed_workflow = (output / ".github/workflows/armproof.yml").read_text()
            self.assertIn(
                f"contract-sha256: {refreshed_contract_digest}", refreshed_workflow
            )
            self.assertTrue((output / "evidence/profiles/manifest.json").is_file())

            with redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(main(["ci", str(output / "armproof.json")]), 1)
            self.assertIn("No measured evidence found", stderr.getvalue())
            self.assertIn("ADOPTION_CHECKLIST.md", stderr.getvalue())

    def test_seal_writes_a_deterministic_ledger_without_claiming_policy_passed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = root / "evidence"
            (evidence / "nested").mkdir(parents=True)
            (evidence / "protocol.json").write_text("{}\n", encoding="utf-8")
            (evidence / "nested" / "requests.jsonl").write_text(
                '{"request_id":"one"}\n', encoding="utf-8"
            )
            config = root / "armproof.json"
            config.write_text(
                json.dumps({
                    "schema_version": "1.0.0",
                    "contract": "contract.json",
                    "evidence": {
                        "adapter": "http-slo-v1",
                        "root": "evidence",
                        "checksums": "evidence/SHA256SUMS",
                        "protocol": "evidence/protocol.json",
                    },
                }),
                encoding="utf-8",
            )
            with redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(main(["seal", str(config)]), 0)
            first = (evidence / "SHA256SUMS").read_text(encoding="utf-8")
            self.assertIn("Sealed 2 evidence files", stdout.getvalue())
            self.assertIn("/opt/armproof/evidence/nested/requests.jsonl", first)
            self.assertIn("/opt/armproof/evidence/protocol.json", first)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["seal", str(config)]), 0)
            self.assertEqual(
                (evidence / "SHA256SUMS").read_text(encoding="utf-8"), first
            )
            with redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(main(["ci", str(config)]), 1)
            self.assertNotIn("checksum", stderr.getvalue().lower())

    def test_init_refuses_to_overwrite_an_existing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "kit"
            output.mkdir()
            (output / "owner.txt").write_text("keep\n", encoding="utf-8")
            with redirect_stderr(io.StringIO()) as stderr:
                status = main([
                    "init",
                    "--endpoint", "http://127.0.0.1:8000/infer",
                    "--output", str(output),
                ])
            self.assertEqual(status, 1)
            self.assertIn("not empty", stderr.getvalue())
            self.assertEqual((output / "owner.txt").read_text(encoding="utf-8"), "keep\n")

    def test_init_rejects_a_non_http_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "kit"
            with redirect_stderr(io.StringIO()) as stderr:
                status = main([
                    "init",
                    "--endpoint", "file:///tmp/model",
                    "--output", str(output),
                ])
            self.assertEqual(status, 1)
            self.assertIn("HTTP(S)", stderr.getvalue())
            self.assertFalse(output.exists())

    def test_lists_installed_adapters(self) -> None:
        with redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(main(["adapters"]), 0)
        payload = json.loads(stdout.getvalue())
        self.assertIn("http-slo-v1", payload["adapters"])

    def test_reference_config_produces_decision_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report"
            with redirect_stdout(io.StringIO()):
                status = main([
                    "ci",
                    str(ROOT / "examples" / "armproof-reference" / "armproof.json"),
                    "--output", str(output),
                ])
            self.assertEqual(status, 0)
            self.assertTrue((output / "index.html").is_file())
            decision = json.loads((output / "decision.json").read_text(encoding="utf-8"))
            self.assertTrue(decision["passed"])
            comparison = json.loads(
                (output / "comparison.json").read_text(encoding="utf-8")
            )
            self.assertEqual(comparison["baseline"]["treatment_id"], "kleidiai-disabled")
            self.assertEqual(comparison["metrics"]["minimum_capacity_ratio"], 2.0)
            receipt = json.loads(
                (output / "verification.json").read_text(encoding="utf-8")
            )
            self.assertEqual(receipt["checksums"]["checked"], 161)
            self.assertIsNone(receipt["reproduction_checksums"])
            self.assertEqual(receipt["comparison_source"], "derived_from_raw_evidence")
            self.assertTrue(receipt["performix"]["passed"])
            self.assertEqual(receipt["performix"]["evidence_source"], "native_arm_performix_code_hotspots_exports")
            self.assertEqual(receipt["performix"]["disabled"]["kai_sample_share"], 0.0)
            self.assertAlmostEqual(
                receipt["performix"]["enabled"]["kai_sample_share"],
                0.673518470835091,
            )
            self.assertGreater(receipt["performix"]["internal_checksums"]["checked"], 20)
            publication = receipt["preregistration_publication"]
            self.assertEqual(publication["experiment_id"], "EXP-2026-014")
            self.assertTrue(publication["plan_embedded_in_measurement_archive"])
            self.assertTrue(publication["plan_embedded_in_project_bundle"])
            self.assertTrue(publication["git_commit_verified_in_checkout"])
            self.assertEqual(
                publication["instance_launch_time_source"],
                "recorded_experiment_metadata",
            )
            self.assertIn("github.com/QasimKhan5x/ArmProof/commit/", publication["public_commit_url"])
            self.assertTrue((output / "deployment-summary.json").is_file())

    def test_reference_ci_rejects_missing_or_tampered_performix_evidence(self) -> None:
        reference = json.loads(
            (ROOT / "examples/armproof-reference/armproof.json").read_text(
                encoding="utf-8"
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing = json.loads(json.dumps(reference))
            for field in ("contract", "deployment_summary"):
                missing[field] = str(
                    (ROOT / "examples/armproof-reference" / missing[field]).resolve()
                )
            missing["supporting_evidence"] = {
                field: str(
                    (
                        ROOT
                        / "examples/armproof-reference"
                        / missing["supporting_evidence"][field]
                    ).resolve()
                )
                for field in ("root", "lock")
            }
            for field in (
                "archive", "preregistration", "analysis_lock", "protocol_lock",
                "workload_manifest", "workload",
            ):
                missing["evidence"][field] = str(
                    (
                        ROOT
                        / "examples/armproof-reference"
                        / missing["evidence"][field]
                    ).resolve()
                )
            missing["evidence"]["raw_quality"] = {
                field: str(
                    (
                        ROOT
                        / "examples/armproof-reference"
                        / missing["evidence"]["raw_quality"][field]
                    ).resolve()
                )
                if field != "ledger_sha256"
                else missing["evidence"]["raw_quality"][field]
                for field in ("root", "checksums", "ledger_sha256", "dataset")
            }
            del missing["evidence"]["performix"]
            missing_path = root / "missing.json"
            missing_path.write_text(json.dumps(missing), encoding="utf-8")
            with redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(main(["ci", str(missing_path)]), 1)
            self.assertIn("performix", stderr.getvalue())

            tampered = json.loads(json.dumps(reference))
            for field in ("contract", "deployment_summary"):
                tampered[field] = str(
                    (ROOT / "examples/armproof-reference" / tampered[field]).resolve()
                )
            tampered["supporting_evidence"] = {
                field: str(
                    (
                        ROOT
                        / "examples/armproof-reference"
                        / tampered["supporting_evidence"][field]
                    ).resolve()
                )
                for field in ("root", "lock")
            }
            evidence = tampered["evidence"]
            for field in (
                "archive", "preregistration", "analysis_lock", "protocol_lock",
                "workload_manifest", "workload",
            ):
                evidence[field] = str(
                    (ROOT / "examples/armproof-reference" / evidence[field]).resolve()
                )
            evidence["raw_quality"] = {
                field: str(
                    (
                        ROOT
                        / "examples/armproof-reference"
                        / evidence["raw_quality"][field]
                    ).resolve()
                )
                if field != "ledger_sha256"
                else evidence["raw_quality"][field]
                for field in ("root", "checksums", "ledger_sha256", "dataset")
            }
            evidence["performix"]["archive"] = str(
                (
                    ROOT
                    / "examples/armproof-reference"
                    / evidence["performix"]["archive"]
                ).resolve()
            )
            evidence["performix"]["preregistration"] = str(
                (
                    ROOT
                    / "examples/armproof-reference"
                    / evidence["performix"]["preregistration"]
                ).resolve()
            )
            evidence["performix"]["archive_sha256"] = "0" * 64
            tampered_path = root / "tampered.json"
            tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
            with redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(main(["ci", str(tampered_path)]), 1)
            self.assertIn("Performix archive SHA-256 mismatch", stderr.getvalue())

    def test_ci_rejects_a_changed_preregistered_contract_digest(self) -> None:
        config = ROOT / "examples/armproof-reference/armproof.json"
        with redirect_stderr(io.StringIO()) as stderr:
            status = main([
                "ci", str(config), "--contract-sha256", "0" * 64,
            ])
        self.assertEqual(status, 1)
        self.assertIn("protected policy digest", stderr.getvalue())

    def test_ci_rejects_checksum_tampering(self) -> None:
        reference = ROOT / "ops/evidence/EXP-2026-004/accepted/evidence"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = root / "SHA256SUMS"
            lines = (reference / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
            lines[0] = f"{'0' * 64}  {lines[0].split(maxsplit=1)[1]}"
            ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
            config = self._write_config(root, checksums=ledger)
            with redirect_stderr(io.StringIO()) as stderr:
                status = main(["ci", str(config)])
            self.assertEqual(status, 1)
            self.assertIn("checksum", stderr.getvalue())

    def test_ci_rejects_reproduction_checksum_tampering(self) -> None:
        reproduction = ROOT / "ops/evidence/EXP-2026-005/accepted/evidence"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = root / "REPRODUCTION-SHA256SUMS"
            lines = (reproduction / "SHA256SUMS").read_text(
                encoding="utf-8"
            ).splitlines()
            lines[-1] = f"{'0' * 64}  {lines[-1].split(maxsplit=1)[1]}"
            ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
            config = self._write_config(root, reproduction_checksums=ledger)
            with redirect_stderr(io.StringIO()) as stderr:
                status = main(["ci", str(config)])
            self.assertEqual(status, 1)
            self.assertIn("reproduction checksum", stderr.getvalue())

    def test_ci_rejects_treatment_identity_not_declared_by_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = json.loads(
                (ROOT / "examples/armproof-reference/contract.json").read_text(
                    encoding="utf-8"
                )
            )
            contract["treatments"][0]["id"] = "forged-disabled"
            contract_path = root / "contract.json"
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            config = self._write_config(root, contract=contract_path)
            with redirect_stderr(io.StringIO()) as stderr:
                status = main(["ci", str(config)])
            self.assertEqual(status, 1)
            self.assertIn("treatment", stderr.getvalue())

    def test_ci_rejects_injected_normalized_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._write_config(root)
            payload = json.loads(config.read_text(encoding="utf-8"))
            payload["comparisons"] = [
                str(ROOT / "examples/fixture-pass/comparison.json")
            ]
            config.write_text(json.dumps(payload), encoding="utf-8")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["ci", str(config)]), 1)

    def test_unknown_config_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "armproof.json"
            config.write_text(json.dumps({
                "schema_version": "1.0.0",
                "contract": "contract.json",
                "comparisons": ["comparison.json"],
                "summary": "summary.json",
                "surprise": True,
            }), encoding="utf-8")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["ci", str(config)]), 1)

    @staticmethod
    def _write_config(
        root: Path,
        *,
        contract: Path | None = None,
        checksums: Path | None = None,
        reproduction_checksums: Path | None = None,
    ) -> Path:
        evidence = ROOT / "ops/evidence/EXP-2026-004/accepted/evidence"
        config = root / "armproof.json"
        config.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "contract": str(
                        contract or ROOT / "examples/armproof-reference/contract.json"
                    ),
                    "evidence": {
                        "adapter": "kleidiai-capacity-v1",
                        "root": str(evidence),
                        "checksums": str(checksums or evidence / "SHA256SUMS"),
                        "workload_manifest": str(
                            ROOT / "data/banking77/generated/manifest.json"
                        ),
                        "reproduction": {
                            "root": str(
                                ROOT / "ops/evidence/EXP-2026-005/accepted/evidence"
                            ),
                            "checksums": str(
                                reproduction_checksums
                                or ROOT
                                / "ops/evidence/EXP-2026-005/accepted/evidence/SHA256SUMS"
                            ),
                        },
                        "performix": {
                            "archive": str(
                                ROOT / "ops/evidence/EXP-2026-010/evidence.tar.gz"
                            ),
                            "archive_sha256": (
                                "28d411e40de38f3ad4a455bbfa09524dee8b44d6e44eb4d3b599e01635789148"
                            ),
                            "experiment_id": "EXP-2026-010",
                            "disabled_run_id": "cbb01b949717",
                            "enabled_run_id": "2bf254d4391b",
                            "linux_perf_kai_cycle_share": 0.6853,
                            "maximum_share_difference": 0.05,
                        },
                    },
                    "deployment_summary": str(
                        ROOT / "examples/armproof-reference/deployment-summary.json"
                    ),
                    "supporting_evidence": {
                        "root": str(
                            ROOT / "ops/evidence/result-first/EXP-2026-002"
                        ),
                        "lock": str(
                            ROOT
                            / "examples/armproof-reference/supporting-evidence-lock.json"
                        ),
                    },
                    "output": str(root / "report"),
                }
            ),
            encoding="utf-8",
        )
        return config


if __name__ == "__main__":
    unittest.main()
