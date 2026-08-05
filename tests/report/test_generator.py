from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from armproof.report import generate_report


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReportGeneratorTests(unittest.TestCase):
    def test_generates_offline_report_and_copies_authoritative_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision = root / "decision.json"
            decision.write_text(json.dumps({
                "schema_version": "1.0.0", "passed": True,
                "claims": [{"claim_id": "safe</script><script>", "status": "pass",
                            "reason_code": "threshold_met", "observed": 2.5, "threshold": 1.5}],
            }))
            summary = root / "summary.json"
            summary.write_text(json.dumps({
                "schema_version": "1.0.0",
                "mixes": {"short": {"ratio": {"baseline_median": .2, "treatment_median": .5, "ratio": 2.5}}},
                "quality_comparison": {"schema_valid_rate": 1.0},
            }))
            comparison = root / "comparison.json"
            comparison.write_text(json.dumps({
                "metrics": {"minimum_capacity_ratio": 2.5},
            }))
            deployment = root / "deployment.json"
            deployment.write_text(json.dumps({
                "schema_version": "1.0.0",
                "experiment_id": "EXP-2026-002",
                "metrics": {
                    "disk_reduction_percent": 35.9,
                    "peak_pss_reduction_percent": 55.3,
                },
                "metric_source": {
                    "experiment_id": "EXP-2026-002",
                    "checksummed_files": 4,
                    "derivation": "locked_aggregate_footprint_and_raw_timing_repetitions",
                },
            }))
            verification = root / "verification.json"
            verification.write_text(json.dumps({
                "schema_version": "1.0.0",
                "comparison_source": "derived_from_raw_evidence",
                "artifact_bindings": {
                    "contract_sha256": "a" * 64,
                    "comparison_sha256": _sha256(comparison),
                    "summary_sha256": _sha256(summary),
                    "decision_sha256": _sha256(decision),
                },
                "checksums": {"passed": True, "checked": 1},
                "reproduction_checksums": None,
                "performix": None,
                "supporting_evidence": {
                    "experiment_id": "EXP-2026-002",
                    "checksummed_files": 4,
                    "derivation": "locked_aggregate_footprint_and_raw_timing_repetitions",
                },
            }))
            output = root / "report"
            index = generate_report(
                decision, summary, output, deployment_summary_path=deployment,
                comparison_path=comparison, verification_path=verification,
            )
            rendered = index.read_text()
            self.assertIn("Measured capacity", rendered)
            self.assertNotIn("</script><script>", rendered)
            self.assertEqual(json.loads((output / "decision.json").read_text())["passed"], True)
            self.assertTrue((output / "data.json").is_file())
            self.assertTrue((output / "deployment-summary.json").is_file())
            self.assertIn("Deployment transformation", rendered)

            changed = json.loads(decision.read_text(encoding="utf-8"))
            changed["claims"][0]["observed"] = 99
            decision.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "verification receipt"):
                generate_report(
                    decision,
                    summary,
                    root / "changed-report",
                    comparison_path=comparison,
                    deployment_summary_path=deployment,
                    verification_path=verification,
                )

    def test_passing_report_requires_bound_comparison_and_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "decision").write_text(
                '{"schema_version":"1.0.0","passed":true,"claims":[]}'
            )
            (root / "summary").write_text(json.dumps({
                "schema_version": "1.0.0",
                "mixes": {"short": {"ratio": {
                    "baseline_median": 1.0, "treatment_median": 2.0, "ratio": 2.0,
                }}},
            }))
            with self.assertRaisesRegex(ValueError, "passing report requires"):
                generate_report(root / "decision", root / "summary", root / "out")

    def test_rejects_wrong_decision_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "decision").write_text('{"schema_version":"0","passed":true}')
            (root / "summary").write_text('{"schema_version":"1.0.0","mixes":{}}')
            with self.assertRaisesRegex(ValueError, "decision"):
                generate_report(root / "decision", root / "summary", root / "out")

    def test_rejects_summary_that_disagrees_with_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "decision").write_text(json.dumps({
                "schema_version": "1.0.0", "passed": True, "claims": [],
            }))
            (root / "summary").write_text(json.dumps({
                "schema_version": "1.0.0",
                "mixes": {"short": {"ratio": {
                    "baseline_median": 1.0, "treatment_median": 2.0, "ratio": 2.0,
                }}},
                "quality_comparison": {"schema_valid_rate": 1.0},
            }))
            (root / "comparison").write_text(json.dumps({
                "metrics": {"minimum_capacity_ratio": 1.5},
            }))
            with self.assertRaisesRegex(ValueError, "disagrees"):
                generate_report(
                    root / "decision", root / "summary", root / "out",
                    comparison_path=root / "comparison",
                )

    def test_rejects_unbounded_verification_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "decision").write_text(
                '{"schema_version":"1.0.0","passed":true,"claims":[]}'
            )
            (root / "summary").write_text(json.dumps({
                "schema_version": "1.0.0",
                "mixes": {"short": {"ratio": {
                    "baseline_median": 1.0, "treatment_median": 2.0, "ratio": 2.0,
                }}},
            }))
            (root / "verification").write_text(json.dumps({
                "schema_version": "1.0.0",
                "comparison_source": "derived_from_raw_evidence",
                "checksums": {"passed": True},
                "reproduction_checksums": {"passed": True},
            }))
            (root / "comparison").write_text(json.dumps({
                "metrics": {"minimum_capacity_ratio": 2.0},
            }))
            with self.assertRaisesRegex(ValueError, "verification receipt"):
                generate_report(
                    root / "decision",
                    root / "summary",
                    root / "out",
                    comparison_path=root / "comparison",
                    verification_path=root / "verification",
                )


if __name__ == "__main__":
    unittest.main()
