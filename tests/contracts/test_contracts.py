from __future__ import annotations

import unittest

from armproof.contracts import ContractError, parse_contract


def valid_contract() -> dict:
    return {
        "schema_version": "1.0.0",
        "contract_id": "phi4-capacity",
        "treatments": [
            {
                "id": "disabled",
                "command": ["serve", "--model", "model"],
                "artifact_sha256": "a" * 64,
                "runtime_sha256": "b" * 64,
                "environment": {"KLEIDIAI": "0"},
            },
            {
                "id": "enabled",
                "command": ["serve", "--model", "model"],
                "artifact_sha256": "a" * 64,
                "runtime_sha256": "b" * 64,
                "environment": {"KLEIDIAI": "1"},
            },
        ],
        "claims": [
            {
                "id": "capacity",
                "causal_scope": "arm_acceleration",
                "comparison_id": "kleidiai-on-off",
                "metric": "throughput_ratio",
                "operator": "gte",
                "threshold": 1.5,
                "required_evidence": ["request_samples", "arm_callchains"],
                "required": True,
                "depends_on": [],
            }
        ],
    }


class ContractTests(unittest.TestCase):
    def test_valid_contract_is_immutable_domain_data(self) -> None:
        contract = parse_contract(valid_contract())
        self.assertEqual(contract.contract_id, "phi4-capacity")
        self.assertEqual(contract.treatments[1].environment["KLEIDIAI"], "1")
        self.assertEqual(contract.claims[0].threshold, 1.5)

    def test_unknown_top_level_field_fails_closed(self) -> None:
        payload = valid_contract()
        payload["surprise"] = True
        with self.assertRaisesRegex(ContractError, "unknown fields"):
            parse_contract(payload)

    def test_duplicate_treatment_id_is_rejected(self) -> None:
        payload = valid_contract()
        payload["treatments"][1]["id"] = "disabled"
        with self.assertRaisesRegex(ContractError, "duplicate treatment"):
            parse_contract(payload)

    def test_invalid_digest_is_rejected(self) -> None:
        payload = valid_contract()
        payload["treatments"][0]["artifact_sha256"] = "not-a-digest"
        with self.assertRaisesRegex(ContractError, "artifact_sha256"):
            parse_contract(payload)

    def test_contract_requires_a_required_claim(self) -> None:
        payload = valid_contract()
        payload["claims"][0]["required"] = False
        with self.assertRaisesRegex(ContractError, "required claim"):
            parse_contract(payload)

    def test_dependency_cycle_is_rejected(self) -> None:
        payload = valid_contract()
        second = dict(payload["claims"][0])
        second["id"] = "quality"
        second["depends_on"] = ["capacity"]
        payload["claims"][0]["depends_on"] = ["quality"]
        payload["claims"].append(second)
        with self.assertRaisesRegex(ContractError, "dependency cycle"):
            parse_contract(payload)


if __name__ == "__main__":
    unittest.main()
