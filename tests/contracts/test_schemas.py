from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class PublicSchemaTests(unittest.TestCase):
    def test_public_schemas_parse_and_reject_unknown_top_level_fields(self) -> None:
        expected = {
            "ci-config.schema.json": "ArmProof CI Config",
            "contract.schema.json": "ArmProof Contract",
            "comparison.schema.json": "ArmProof Normalized Comparison",
            "decision.schema.json": "ArmProof Decision",
            "evidence-manifest.schema.json": "ArmProof Evidence Manifest",
            "experiment.schema.json": "ArmProof Experiment Record",
        }
        for filename, title in expected.items():
            with self.subTest(filename=filename):
                schema = json.loads((ROOT / "schemas" / filename).read_text(encoding="utf-8"))
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
                self.assertEqual(schema["title"], title)
                self.assertFalse(schema["additionalProperties"])

    def test_ci_schema_covers_the_reference_adapter_and_optional_evidence(self) -> None:
        schema = json.loads(
            (ROOT / "schemas/ci-config.schema.json").read_text(encoding="utf-8")
        )
        adapter_constants = {
            branch.get("properties", {}).get("adapter", {}).get("const")
            for branch in schema["properties"]["evidence"]["oneOf"]
        }
        self.assertIn("kleidiai-confirmed-v2", adapter_constants)
        confirmed = next(
            branch for branch in schema["properties"]["evidence"]["oneOf"]
            if branch.get("properties", {}).get("adapter", {}).get("const")
            == "kleidiai-confirmed-v2"
        )
        self.assertIn("memory_optimization", confirmed["required"])
        self.assertFalse(
            confirmed["properties"]["memory_optimization"]["additionalProperties"]
        )
        self.assertIn("publication_proof", schema["properties"])
        self.assertIn("supporting_evidence", schema["properties"])


if __name__ == "__main__":
    unittest.main()
