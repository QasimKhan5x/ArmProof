from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from armproof.cli import main
from armproof.contracts import parse_contract
from armproof.evidence.adapters import (
    _require_aws_graviton_binding,
    _bound_file,
    get_evidence_adapter,
    list_evidence_adapters,
)


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


def _load_http_example(name: str):
    script = Path(__file__).resolve().parents[2] / "examples/http-slo/build_example.py"
    spec = importlib.util.spec_from_file_location(name, script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rebind_evidence(root: Path) -> None:
    evidence = root / "evidence"
    files = sorted(
        path for path in evidence.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    (evidence / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
        f"/opt/armproof/evidence/{path.relative_to(evidence).as_posix()}\n"
        for path in files
    ), encoding="utf-8")


class EvidenceAdapterTests(unittest.TestCase):
    def test_reference_graviton_binding_rejects_generic_arm_machine(self) -> None:
        with self.assertRaisesRegex(ValueError, "AWS Graviton"):
            _require_aws_graviton_binding({
                "machine": {
                    "bios_vendor_id": "Generic",
                    "bios_model_name": "Arm server",
                    "model_name": "Neoverse-N1",
                }
            })
        _require_aws_graviton_binding({
            "machine": {
                "bios_vendor_id": "AWS",
                "bios_model_name": "AWS Graviton4",
                "model_name": "Neoverse-V2",
            }
        })

    def test_generic_http_adapter_derives_bracket_from_raw_requests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            module = _load_http_example("http_slo_example")
            config_path = module.build(root)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            contract = parse_contract(json.loads(
                (root / "contract.json").read_text(encoding="utf-8")
            ))

            verified = get_evidence_adapter("http-slo-v1").verify(
                contract,
                config["evidence"],
                root,
            )

            self.assertAlmostEqual(
                verified.comparison.metrics["tested_capacity_ratio"], 3.0
            )
            self.assertAlmostEqual(
                verified.comparison.metrics["capacity_ratio_lower_bound"], 2.0
            )
            self.assertTrue(verified.comparison.arm_path_treatment_observed)
            self.assertFalse(verified.comparison.arm_path_baseline_observed)
            self.assertEqual(verified.comparison.metrics["schema_valid_rate"], 1.0)
            self.assertIsNone(verified.reproduction_checksums)
            output = root / "report"

            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(["ci", str(config_path), "--output", str(output)]),
                    0,
                )
            self.assertTrue((output / "index.html").is_file())
            receipt = json.loads(
                (output / "verification.json").read_text(encoding="utf-8")
            )
            self.assertIsNone(receipt["reproduction_checksums"])

    def test_generic_adapter_rejects_staged_arm_profile_and_undeclared_controls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            module = _load_http_example("http_slo_example_negative")
            config = module.build(root)

            baseline = root / "evidence/baseline.perf"
            baseline.write_text(
                baseline.read_text(encoding="utf-8").replace(
                    "generic_matmul", "kai_matmul_clamp"
                ),
                encoding="utf-8",
            )
            profile_manifest = root / "evidence/profiles/manifest.json"
            profile_payload = json.loads(profile_manifest.read_text(encoding="utf-8"))
            profile_payload["runs"]["baseline"]["report_sha256"] = hashlib.sha256(
                baseline.read_bytes()
            ).hexdigest()
            profile_manifest.write_text(json.dumps(profile_payload), encoding="utf-8")
            _rebind_evidence(root)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["ci", str(config)]), 2)

            identities = root / "evidence/identities.json"
            payload = json.loads(identities.read_text(encoding="utf-8"))
            payload["baseline"]["controls"]["threads"] = 99
            identities.write_text(json.dumps(payload), encoding="utf-8")
            _rebind_evidence(root)
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["ci", str(config)]), 1)

    def test_generic_adapter_rejects_reused_confirmation_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            config_path = _load_http_example("http_slo_duplicate").build(root)
            protocol_path = root / "evidence/protocol.json"
            protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
            first = protocol["boundaries"]["baseline"]["pass"][0]
            protocol["boundaries"]["baseline"]["pass"] = [first, first, first]
            protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
            _rebind_evidence(root)

            with self.assertRaisesRegex(ValueError, "distinct confirmation files"):
                config = json.loads(config_path.read_text(encoding="utf-8"))
                contract = parse_contract(json.loads(
                    (root / "contract.json").read_text(encoding="utf-8")
                ))
                get_evidence_adapter("http-slo-v1").verify(
                    contract, config["evidence"], root
                )

    def test_generic_adapter_rejects_impossible_measurement_cadence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            config_path = _load_http_example("http_slo_cadence").build(root)
            path = root / "evidence/requests/baseline-pass-1.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            for row in rows:
                row["scheduled_ns"] = 0
                row["started_ns"] = 0
                row["finished_ns"] = int(row["latency_ms"] * 1_000_000)
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            _rebind_evidence(root)

            with self.assertRaisesRegex(ValueError, "measurement cadence"):
                config = json.loads(config_path.read_text(encoding="utf-8"))
                contract = parse_contract(json.loads(
                    (root / "contract.json").read_text(encoding="utf-8")
                ))
                get_evidence_adapter("http-slo-v1").verify(
                    contract, config["evidence"], root
                )

    def test_generic_adapter_counts_dispatch_backlog_in_slo_latency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            config_path = _load_http_example("http_slo_dispatch_backlog").build(root)
            path = root / "evidence/requests/baseline-pass-1.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            for row in rows:
                delay_ns = 60_000_000_000
                row["started_ns"] += delay_ns
                row["finished_ns"] += delay_ns
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            _rebind_evidence(root)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            contract = parse_contract(json.loads(
                (root / "contract.json").read_text(encoding="utf-8")
            ))

            with self.assertRaisesRegex(ValueError, "pass evidence disagrees"):
                get_evidence_adapter("http-slo-v1").verify(
                    contract, config["evidence"], root
                )

    def test_generic_adapter_requires_quality_release_claims(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            config_path = _load_http_example("http_slo_quality_claims").build(root)
            contract_path = root / "contract.json"
            contract_payload = json.loads(contract_path.read_text(encoding="utf-8"))
            contract_payload["claims"] = [
                claim for claim in contract_payload["claims"]
                if not claim["metric"].startswith(("accuracy_", "macro_f1_", "schema_"))
            ]
            for claim in contract_payload["claims"]:
                claim["depends_on"] = []
            contract = parse_contract(contract_payload)
            config = json.loads(config_path.read_text(encoding="utf-8"))

            with self.assertRaisesRegex(ValueError, "required quality claims"):
                get_evidence_adapter("http-slo-v1").verify(
                    contract, config["evidence"], root
                )

    def test_generic_adapter_rejects_non_protective_quality_claim_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            config_path = _load_http_example("http_slo_quality_shape").build(root)
            contract_payload = json.loads(
                (root / "contract.json").read_text(encoding="utf-8")
            )
            accuracy = next(
                claim for claim in contract_payload["claims"]
                if claim["metric"] == "accuracy_delta_pp"
            )
            accuracy["operator"] = "lte"
            accuracy["threshold"] = 100
            contract = parse_contract(contract_payload)
            config = json.loads(config_path.read_text(encoding="utf-8"))

            with self.assertRaisesRegex(ValueError, "required quality claims"):
                get_evidence_adapter("http-slo-v1").verify(
                    contract, config["evidence"], root
                )

    def test_generic_adapter_rejects_vacuous_quality_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            config_path = _load_http_example("http_slo_vacuous_quality").build(root)
            contract_payload = json.loads(
                (root / "contract.json").read_text(encoding="utf-8")
            )
            for claim in contract_payload["claims"]:
                if claim["metric"] in {"accuracy_delta_pp", "macro_f1_delta_pp"}:
                    claim["threshold"] = -100000.0
                elif claim["metric"] == "schema_valid_rate":
                    claim["threshold"] = 0.0
            contract = parse_contract(contract_payload)
            config = json.loads(config_path.read_text(encoding="utf-8"))

            with self.assertRaisesRegex(ValueError, "classification loss"):
                get_evidence_adapter("http-slo-v1").verify(
                    contract, config["evidence"], root
                )

    def test_generic_adapter_rejects_reused_quality_lane_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            config_path = _load_http_example("http_slo_quality_reuse").build(root)
            protocol_path = root / "evidence/protocol.json"
            protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
            protocol["quality"]["treatment_samples"] = protocol["quality"][
                "baseline_samples"
            ]
            protocol_path.write_text(
                json.dumps(protocol, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _rebind_evidence(root)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            contract = parse_contract(json.loads(
                (root / "contract.json").read_text(encoding="utf-8")
            ))

            with self.assertRaisesRegex(ValueError, "distinct lane artifacts"):
                get_evidence_adapter("http-slo-v1").verify(
                    contract, config["evidence"], root
                )

    def test_generic_adapter_binds_workload_and_profiler_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            config_path = _load_http_example("http_slo_bindings").build(root)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            contract = parse_contract(json.loads(
                (root / "contract.json").read_text(encoding="utf-8")
            ))
            workload = root / "evidence/identity-sources/quality.jsonl"
            workload.write_text(
                workload.read_text(encoding="utf-8").replace("card request", "changed text"),
                encoding="utf-8",
            )
            _rebind_evidence(root)
            with self.assertRaisesRegex(ValueError, "workload manifest hash mismatch"):
                get_evidence_adapter("http-slo-v1").verify(
                    contract, config["evidence"], root
                )

            _load_http_example("http_slo_bindings_rebuilt").build(root.parent / "kit2")
            root = root.parent / "kit2"
            config = json.loads((root / "armproof.json").read_text(encoding="utf-8"))
            contract = parse_contract(json.loads(
                (root / "contract.json").read_text(encoding="utf-8")
            ))
            capture = root / "evidence/treatment.perf"
            capture.write_bytes(capture.read_bytes() + b"tampered")
            _rebind_evidence(root)
            with self.assertRaisesRegex(ValueError, "profile manifest hash mismatch"):
                get_evidence_adapter("http-slo-v1").verify(
                    contract, config["evidence"], root
                )

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

    def test_adapter_listing_includes_builtins_and_plugins(self) -> None:
        entry = unittest.mock.Mock()
        entry.name = "external-v1"
        entries = unittest.mock.Mock()
        entries.select.return_value = [entry]
        with patch("armproof.evidence.adapters.entry_points", return_value=entries):
            self.assertEqual(
                list_evidence_adapters(),
                (
                    "external-v1",
                    "http-slo-v1",
                    "kleidiai-capacity-v1",
                    "kleidiai-sustained-v1",
                ),
            )

    def test_sustained_adapter_derives_the_conservative_release_decision(self) -> None:
        root = Path(__file__).resolve().parents[2]
        contract = parse_contract(json.loads(
            (root / "examples/armproof-reference/sustained-contract.json").read_text()
        ))

        config = {
                "adapter": "kleidiai-sustained-v1",
                "archive": str(root / "ops/evidence/EXP-2026-009/evidence.tar.gz"),
                "archive_sha256": (
                    "f22e647aabe40eefd2abc5548306f40e2a5558ce1a85bc31c18319e6e51d78da"
                ),
                "workload_manifest": str(
                    root / "data/banking77/generated/manifest.json"
                ),
                "performix": {
                    "archive": str(root / "ops/evidence/EXP-2026-010/evidence.tar.gz"),
                    "archive_sha256": (
                        "28d411e40de38f3ad4a455bbfa09524dee8b44d6e44eb4d3b599e01635789148"
                    ),
                    "experiment_id": "EXP-2026-010",
                    "disabled_run_id": "cbb01b949717",
                    "enabled_run_id": "2bf254d4391b",
                    "linux_perf_kai_cycle_share": 0.6853,
                    "maximum_share_difference": 0.05,
                },
            }
        verified = get_evidence_adapter("kleidiai-sustained-v1").verify(
            contract,
            config,
            Path("/"),
        )

        self.assertEqual(verified.adapter, "kleidiai-sustained-v1")
        self.assertEqual(verified.comparison.metrics["minimum_capacity_ratio"], 2.0)
        self.assertEqual(verified.summary["raw_confirmation_samples"], 4200)
        self.assertEqual(verified.summary["trial_matrix"][3]["outcomes"], [
            "fail", "pass", "fail", "fail", "fail",
        ])
        self.assertEqual(verified.checksums.checked, 69)
        self.assertIsNone(verified.reproduction_checksums)
        self.assertTrue(verified.performix["passed"])
        self.assertEqual(
            verified.performix["identity_binding"]["runtime_sha256"],
            verified.comparison.baseline.runtime_sha256,
        )
        self.assertEqual(
            verified.performix["identity_binding"]["machine"]["bios_vendor_id"],
            "AWS",
        )
        self.assertIn(
            "AWS Graviton4",
            verified.performix["identity_binding"]["machine"]["bios_model_name"],
        )

        config["performix"]["linux_perf_kai_cycle_share"] = 0.625
        with self.assertRaisesRegex(ValueError, "sustained archive"):
            get_evidence_adapter("kleidiai-sustained-v1").verify(
                contract, config, Path("/")
            )


if __name__ == "__main__":
    unittest.main()
