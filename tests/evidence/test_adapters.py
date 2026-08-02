from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from armproof.cli import main
from armproof.contracts import parse_contract
from armproof.evidence.adapters import _bound_file, get_evidence_adapter


def _sample(request_id: str, latency_ms: float) -> str:
    finished = int(latency_ms * 1_000_000)
    return json.dumps({
        "request_id": request_id,
        "scheduled_ns": 0,
        "started_ns": 0,
        "finished_ns": finished,
        "latency_ms": latency_ms,
        "status_code": 200,
        "error": None,
        "response": {"request_id": request_id},
    })


class EvidenceAdapterTests(unittest.TestCase):
    def test_generic_http_adapter_derives_bracket_from_raw_requests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            groups = {
                "baseline-pass": (2, 1000.0),
                "baseline-fail": (3, 12_000.0),
                "treatment-pass": (6, 1000.0),
                "treatment-fail": (7, 12_000.0),
            }
            boundaries: dict[str, dict[str, list[str]]] = {
                "baseline": {"pass": [], "fail": []},
                "treatment": {"pass": [], "fail": []},
            }
            for group, (count, latency) in groups.items():
                treatment, outcome = group.split("-")
                for repetition in range(3):
                    path = root / f"{group}-{repetition + 1}.jsonl"
                    path.write_text("\n".join(
                        _sample(f"{group}-{repetition}-{index}", latency)
                        for index in range(count)
                    ) + "\n", encoding="utf-8")
                    boundaries[treatment][outcome].append(path.name)
            (root / "baseline.perf").write_text("python\n", encoding="utf-8")
            (root / "treatment.perf").write_text("kai_matmul_clamp\n", encoding="utf-8")
            digest = "a" * 64
            (root / "identities.json").write_text(json.dumps({
                "schema_version": "1.0.0",
                "baseline": {
                    "treatment_id": "baseline",
                    "artifact_sha256": digest,
                    "runtime_sha256": digest,
                    "workload_sha256": digest,
                    "environment_sha256": digest,
                    "controls": {"mode": "baseline"},
                },
                "treatment": {
                    "treatment_id": "optimized",
                    "artifact_sha256": digest,
                    "runtime_sha256": digest,
                    "workload_sha256": digest,
                    "environment_sha256": digest,
                    "controls": {"mode": "optimized"},
                },
            }), encoding="utf-8")
            protocol = root / "protocol.json"
            protocol.write_text(json.dumps({
                "schema_version": "1.0.0",
                "comparison_id": "generic-http-comparison",
                "measurement_seconds": 10.0,
                "p95_slo_ms": 10_000.0,
                "max_error_rate": 0.01,
                "minimum_delivery_ratio": 0.95,
                "minimum_requests_per_file": 1,
                "baseline_treatment_id": "baseline",
                "treatment_treatment_id": "optimized",
                "identity_manifest": "identities.json",
                "boundaries": boundaries,
                "arm_attribution": {
                    "baseline_profile": "baseline.perf",
                    "treatment_profile": "treatment.perf",
                    "symbol_regex": "kai_",
                },
            }), encoding="utf-8")
            files = [path for path in root.iterdir() if path.name != "SHA256SUMS"]
            ledger = root / "SHA256SUMS"
            ledger.write_text("".join(
                f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
                f"/opt/armproof/evidence/{path.name}\n"
                for path in sorted(files)
            ), encoding="utf-8")
            contract_payload = {
                "schema_version": "1.0.0",
                "contract_id": "generic-http",
                "treatments": [
                    {
                        "id": treatment_id,
                        "command": ["service"],
                        "artifact_sha256": digest,
                        "runtime_sha256": digest,
                        "workload_sha256": digest,
                        "environment_sha256": digest,
                        "environment": {"mode": treatment_id},
                    }
                    for treatment_id in ("baseline", "optimized")
                ],
                "claims": [{
                    "id": "capacity",
                    "causal_scope": "cloud_capacity",
                    "comparison_id": "generic-http-comparison",
                    "metric": "tested_capacity_ratio",
                    "operator": "gte",
                    "threshold": 2.0,
                    "required_evidence": ["request_samples", "boundary_confirmations"],
                    "required": True,
                    "depends_on": [],
                }],
            }
            contract = parse_contract(contract_payload)

            verified = get_evidence_adapter("http-slo-v1").verify(
                contract,
                {
                    "adapter": "http-slo-v1",
                    "root": str(root),
                    "checksums": str(ledger),
                    "protocol": str(protocol),
                },
                Path("/"),
            )

            self.assertAlmostEqual(
                verified.comparison.metrics["tested_capacity_ratio"], 3.0
            )
            self.assertAlmostEqual(
                verified.comparison.metrics["capacity_ratio_lower_bound"], 2.0
            )
            self.assertTrue(verified.comparison.arm_path_treatment_observed)
            self.assertFalse(verified.comparison.arm_path_baseline_observed)
            self.assertIsNone(verified.reproduction_checksums)

            contract_path = root / "contract.json"
            contract_path.write_text(json.dumps(contract_payload), encoding="utf-8")
            config_path = root / "armproof.json"
            config_path.write_text(json.dumps({
                "schema_version": "1.0.0",
                "contract": "contract.json",
                "evidence": {
                    "adapter": "http-slo-v1",
                    "root": ".",
                    "checksums": "SHA256SUMS",
                    "protocol": "protocol.json",
                },
            }), encoding="utf-8")
            output = root / "report"

            self.assertEqual(
                main(["ci", str(config_path), "--output", str(output)]),
                0,
            )
            self.assertTrue((output / "index.html").is_file())
            receipt = json.loads(
                (output / "verification.json").read_text(encoding="utf-8")
            )
            self.assertIsNone(receipt["reproduction_checksums"])

    def test_external_adapter_can_be_discovered_by_entry_point(self) -> None:
        plugin = object()
        entry = unittest.mock.Mock()
        entry.name = "external-v1"
        entry.load.return_value = plugin
        entries = unittest.mock.Mock()
        entries.select.return_value = [entry]
        with patch("armproof.evidence.adapters.entry_points", return_value=entries):
            self.assertIs(get_evidence_adapter("external-v1"), plugin)

    def test_generic_adapter_rejects_unbound_and_outside_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            root.mkdir()
            unbound = root / "unbound.jsonl"
            unbound.write_text("{}\n", encoding="utf-8")
            outside = root.parent / "outside.jsonl"
            outside.write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "absent from the checksum"):
                _bound_file(root, unbound, set(), "boundary")
            with self.assertRaisesRegex(ValueError, "inside the evidence root"):
                _bound_file(root, outside, {"../outside.jsonl"}, "boundary")

    def test_unknown_adapter_fails_with_available_adapter_names(self) -> None:
        with self.assertRaisesRegex(ValueError, "http-slo-v1"):
            get_evidence_adapter("missing-v1")


if __name__ == "__main__":
    unittest.main()
