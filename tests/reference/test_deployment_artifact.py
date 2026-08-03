from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class DeploymentArtifactTests(unittest.TestCase):
    def test_passing_manifest_matches_accepted_artifact_and_runtime(self) -> None:
        manifest = json.loads((
            ROOT / "examples" / "phi4-graviton" / "passing-deployment.json"
        ).read_text(encoding="utf-8"))
        identities = json.loads((
            ROOT / "ops" / "evidence" / "EXP-2026-004" / "accepted" / "evidence"
            / "capacity" / "artifact-identities.json"
        ).read_text(encoding="utf-8"))
        runtime = json.loads((
            ROOT / "ops" / "evidence" / "EXP-2026-004" / "accepted" / "evidence"
            / "runtime-lock.json"
        ).read_text(encoding="utf-8"))
        contract = json.loads((
            ROOT / "examples" / "armproof-reference" / "sustained-contract.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "verified_by_armproof")
        self.assertEqual(manifest["hardware"]["architecture"], "arm64")
        self.assertEqual(
            manifest["model"]["source_artifact_sha256"], identities["source"]["sha256"]
        )
        self.assertEqual(
            manifest["model"]["enabled_overlay_sha256"], identities["enabled"]["sha256"]
        )
        self.assertEqual(
            manifest["runtime"]["onnxruntime_commit"], runtime["onnxruntime"]
        )
        self.assertEqual(
            manifest["service"]["session_options"]["mlas.disable_kleidiai"], "0"
        )
        self.assertEqual(
            manifest["model"]["source_artifact_sha256"],
            contract["treatments"][1]["artifact_sha256"],
        )
        capacity_claim = next(
            row
            for row in contract["claims"]
            if row["id"] == "sustained-capacity-lower-bound"
        )
        self.assertEqual(
            manifest["accepted_result"]["minimum_fixed_slo_capacity_ratio"],
            capacity_claim["threshold"],
        )

    def test_systemd_unit_uses_verified_enabled_overlay(self) -> None:
        unit = (ROOT / "deploy" / "armproof-phi4.service").read_text(encoding="utf-8")
        environment = (ROOT / "deploy" / "phi4.env.example").read_text(encoding="utf-8")
        self.assertIn("--backend ort-int4", unit)
        self.assertIn("--threads 16", unit)
        self.assertIn("kleidiai-enabled", environment)
        self.assertIn("NoNewPrivileges=true", unit)


if __name__ == "__main__":
    unittest.main()
