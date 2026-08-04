from __future__ import annotations

import json
import io
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
                "ADOPTION_CHECKLIST.md",
                "README.md",
                ".github/workflows/armproof.yml",
            }
            self.assertTrue(all((output / relative).is_file() for relative in expected))
            plan = json.loads(
                (output / "collection-plan.json").read_text(encoding="utf-8")
            )
            self.assertEqual(plan["endpoint"], "http://127.0.0.1:8000/infer")
            config = json.loads((output / "armproof.json").read_text(encoding="utf-8"))
            self.assertEqual(config["evidence"]["adapter"], "http-slo-v1")
            workflow = (output / ".github/workflows/armproof.yml").read_text(
                encoding="utf-8"
            )
            self.assertIn("QasimKhan5x/ArmProof@v0.5.1", workflow)

            with redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(main(["ci", str(output / "armproof.json")]), 1)
            self.assertIn("evidence", stderr.getvalue())

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
            self.assertEqual(comparison["metrics"]["minimum_capacity_ratio"], 2.5)
            receipt = json.loads(
                (output / "verification.json").read_text(encoding="utf-8")
            )
            self.assertEqual(receipt["checksums"]["checked"], 141)
            self.assertEqual(receipt["reproduction_checksums"]["checked"], 141)
            self.assertEqual(receipt["comparison_source"], "derived_from_raw_evidence")
            self.assertTrue((output / "deployment-summary.json").is_file())

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
                str(ROOT / "examples/armproof-reference/comparison.json")
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
                    },
                    "deployment_summary": str(
                        ROOT / "examples/armproof-reference/deployment-summary.json"
                    ),
                    "output": str(root / "report"),
                }
            ),
            encoding="utf-8",
        )
        return config


if __name__ == "__main__":
    unittest.main()
