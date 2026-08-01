from __future__ import annotations

import unittest

from armproof.evidence import EvidenceRecordError, parse_comparison


def identity(treatment_id: str, enabled: bool) -> dict:
    return {
        "treatment_id": treatment_id,
        "artifact_sha256": "a" * 64,
        "runtime_sha256": "b" * 64,
        "workload_sha256": "c" * 64,
        "environment_sha256": "d" * 64,
        "controls": {"kleidiai.enabled": enabled, "threads": 16},
    }


def record() -> dict:
    return {
        "schema_version": "1.0.0",
        "comparison_id": "on-off",
        "causal_scope": "arm_acceleration",
        "baseline": identity("disabled", False),
        "treatment": identity("enabled", True),
        "metrics": {"throughput_ratio": 1.6},
        "evidence_kinds": ["request_samples", "arm_callchains"],
        "arm_attribution": {"baseline_observed": False, "treatment_observed": True},
    }


class ComparisonRecordTests(unittest.TestCase):
    def test_parses_valid_comparison(self) -> None:
        parsed = parse_comparison(record())
        self.assertEqual(parsed.metrics["throughput_ratio"], 1.6)
        self.assertTrue(parsed.treatment.controls["kleidiai.enabled"])

    def test_rejects_non_finite_metric(self) -> None:
        payload = record()
        payload["metrics"]["throughput_ratio"] = float("nan")
        with self.assertRaisesRegex(EvidenceRecordError, "finite"):
            parse_comparison(payload)

    def test_rejects_unknown_evidence_semantics(self) -> None:
        payload = record()
        payload["invented"] = "field"
        with self.assertRaisesRegex(EvidenceRecordError, "unknown fields"):
            parse_comparison(payload)


if __name__ == "__main__":
    unittest.main()
