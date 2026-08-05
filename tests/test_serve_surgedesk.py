from __future__ import annotations

import base64
import io
import json
import unittest
import zipfile
from unittest.mock import patch

from scripts.serve_surgedesk import (
    DeploymentState,
    _adoption_receipt,
    _match_lane_identity,
    _probe_lane,
    _response_identity_matches,
    _upstream_request,
    handler_for,
)


class SurgeDeskGatewayTests(unittest.TestCase):
    def test_adoption_action_generates_and_validates_a_real_starter(self) -> None:
        receipt = _adoption_receipt()
        self.assertEqual(receipt["validation_status"], "BLOCKED")
        self.assertNotEqual(receipt["initial_ci_exit_code"], 0)
        self.assertEqual(
            receipt["initial_ci_reason"],
            "no measured evidence found",
        )
        self.assertIn("measured evidence is absent", receipt["validation_detail"])
        self.assertIn("bound to this contract digest", receipt["validation_detail"])
        self.assertIn("contract.json", receipt["generated_files"])
        self.assertIn(".github/workflows/armproof.yml", receipt["generated_files"])
        self.assertIn("QasimKhan5x/ArmProof@v0.9.0", receipt["workflow"])
        self.assertEqual(len(receipt["contract_sha256"]), 64)
        self.assertEqual(receipt["archive_name"], "armproof-service-starter.zip")
        with zipfile.ZipFile(
            io.BytesIO(base64.b64decode(receipt["archive_base64"]))
        ) as archive:
            names = set(archive.namelist())
        self.assertIn("my-arm-service/contract.json", names)
        self.assertIn("my-arm-service/.github/workflows/armproof.yml", names)

    def test_deployment_cannot_promote_before_a_passing_fresh_audit(self) -> None:
        state = DeploymentState(active_lane="baseline")
        live_identity = {
            "model_identity": "b" * 64,
            "source_artifact_sha256": "a" * 64,
            "runtime_lock_sha256": "c" * 64,
            "runtime_artifact_ledger_sha256": "e" * 64,
            "runtime": "onnxruntime-genai",
            "runtime_version": "0.15.0.dev0",
            "architecture": "aarch64",
            "threads_per_lane": 16,
            "cpu_affinity": list(range(16)),
            "instance_type": "c8g.4xlarge",
            "instance_identity_source": "aws-imdsv2",
            "baseline_control": "1",
            "optimized_control": "0",
        }
        audited = {
            "model_identity": "b" * 64,
            "source_artifact_sha256": "a" * 64,
            "runtime_lock_sha256": "c" * 64,
            "runtime_artifact_ledger_sha256": "e" * 64,
            "runtime": "onnxruntime-genai",
            "runtime_version": "0.15.0.dev0",
            "architecture": "aarch64",
            "threads": 16,
            "cpu_affinity": list(range(16)),
            "instance_type": "c8g.4xlarge",
            "instance_identity_source": "aws-imdsv2",
            "controls": {
                "baseline": {"mlas.disable_kleidiai": "1"},
                "optimized": {"mlas.disable_kleidiai": "0"},
            },
        }
        with self.assertRaisesRegex(ValueError, "fresh passing audit"):
            state.promote(live_identity)

        state.record_audit({"passed": False, "experiment_id": "EXP-failed"})
        with self.assertRaisesRegex(ValueError, "fresh passing audit"):
            state.promote(live_identity)

        state.record_audit({
            "passed": True,
            "experiment_id": "EXP-2026-014",
            "deployment_identity": audited,
        })
        promoted = state.promote(live_identity)
        self.assertEqual(promoted["active_lane"], "optimized")
        self.assertEqual(promoted["audit_experiment_id"], "EXP-2026-014")
        self.assertTrue(promoted["release_ready"])
        self.assertIsNotNone(promoted["promoted_at"])

        state.active_lane = "baseline"
        swapped = {**live_identity, "source_artifact_sha256": "b" * 64}
        with self.assertRaisesRegex(ValueError, "differs from audited"):
            state.promote(swapped)
        for field, value in (
            ("model_identity", "d" * 64),
            ("runtime_lock_sha256", "e" * 64),
            ("instance_type", "c8g.8xlarge"),
            ("cpu_affinity", list(range(1, 17))),
        ):
            with self.subTest(field=field):
                state.active_lane = "baseline"
                with self.assertRaisesRegex(ValueError, "differs from audited"):
                    state.promote({**live_identity, field: value})

        state.active_lane = "optimized"
        self.assertEqual(
            state.authorize_active_route("optimized", {
                "model_identity": live_identity["model_identity"],
                "source_artifact_sha256": live_identity["source_artifact_sha256"],
                "runtime_lock_sha256": live_identity["runtime_lock_sha256"],
                "runtime_artifact_ledger_sha256": live_identity["runtime_artifact_ledger_sha256"],
                "runtime": live_identity["runtime"],
                "runtime_version": live_identity["runtime_version"],
                "architecture": live_identity["architecture"],
                "threads": live_identity["threads_per_lane"],
                "cpu_affinity": live_identity["cpu_affinity"],
                "instance_type": live_identity["instance_type"],
                "instance_identity_source": live_identity["instance_identity_source"],
                "optimization_control": {"mlas.disable_kleidiai": "0"},
            }),
            "EXP-2026-014",
        )
        drifted = {
            "model_identity": "f" * 64,
            "source_artifact_sha256": live_identity["source_artifact_sha256"],
            "runtime_lock_sha256": live_identity["runtime_lock_sha256"],
            "runtime_artifact_ledger_sha256": live_identity["runtime_artifact_ledger_sha256"],
            "runtime": live_identity["runtime"],
            "runtime_version": live_identity["runtime_version"],
            "architecture": live_identity["architecture"],
            "threads": live_identity["threads_per_lane"],
            "cpu_affinity": live_identity["cpu_affinity"],
            "instance_type": live_identity["instance_type"],
            "instance_identity_source": live_identity["instance_identity_source"],
            "optimization_control": {"mlas.disable_kleidiai": "0"},
        }
        with self.assertRaisesRegex(ValueError, "drifted from audited release"):
            state.authorize_active_route("optimized", drifted)
        self.assertEqual(state.snapshot()["active_lane"], "baseline")
        self.assertIsNone(state.snapshot()["audit_experiment_id"])

    def test_upstream_request_binds_the_expected_backend_and_request_id(self) -> None:
        response = io.BytesIO(json.dumps({
            "request_id": "surge-run-1",
            "backend": "kleidiai-enabled",
            "output": '{"intent":"card_arrival"}',
        }).encode())

        with patch("scripts.serve_surgedesk.urllib.request.urlopen", return_value=response):
            payload, elapsed_ms, started_at = _upstream_request(
                "http://127.0.0.1:8001/infer",
                text="Where is my card?",
                categories=["card_arrival"],
                request_id="surge-run-1",
                expected_backend="kleidiai-enabled",
            )

        self.assertEqual(payload["backend"], "kleidiai-enabled")
        self.assertGreaterEqual(elapsed_ms, 0)
        self.assertIn("+00:00", started_at)

    def test_upstream_request_rejects_a_swapped_treatment(self) -> None:
        response = io.BytesIO(json.dumps({
            "request_id": "surge-run-1",
            "backend": "kleidiai-disabled",
            "output": '{"intent":"card_arrival"}',
        }).encode())

        with patch("scripts.serve_surgedesk.urllib.request.urlopen", return_value=response):
            with self.assertRaisesRegex(ValueError, "backend identity mismatch"):
                _upstream_request(
                    "http://127.0.0.1:8001/infer",
                    text="Where is my card?",
                    categories=["card_arrival"],
                    request_id="surge-run-1",
                    expected_backend="kleidiai-enabled",
                )

    def test_upstream_request_rejects_a_wrong_request_id(self) -> None:
        response = io.BytesIO(json.dumps({
            "request_id": "different-request",
            "backend": "kleidiai-enabled",
            "output": '{"intent":"card_arrival"}',
        }).encode())

        with patch("scripts.serve_surgedesk.urllib.request.urlopen", return_value=response):
            with self.assertRaisesRegex(ValueError, "request identity mismatch"):
                _upstream_request(
                    "http://127.0.0.1:8001/infer",
                    text="Where is my card?",
                    categories=["card_arrival"],
                    request_id="surge-run-1",
                    expected_backend="kleidiai-enabled",
                )

    def test_matched_endpoints_require_distinct_urls_and_compatible_cores(self) -> None:
        with self.assertRaisesRegex(ValueError, "distinct"):
            handler_for(
                baseline_endpoint="http://same/infer",
                optimized_endpoint="http://same/infer",
            )
        with self.assertRaisesRegex(ValueError, "equal size"):
            handler_for(
                baseline_endpoint="http://baseline/infer",
                optimized_endpoint="http://optimized/infer",
                baseline_cores="0-3",
                optimized_cores="4-9",
            )
        with self.assertRaisesRegex(ValueError, "identical or disjoint"):
            handler_for(
                baseline_endpoint="http://baseline/infer",
                optimized_endpoint="http://optimized/infer",
                baseline_cores="0-7",
                optimized_cores="7-14",
            )
        handler_for(
            baseline_endpoint="http://baseline/infer",
            optimized_endpoint="http://optimized/infer",
            baseline_cores="0-15",
            optimized_cores="0-15",
        )

    def test_lane_probe_verifies_backend_and_actual_cpu_affinity(self) -> None:
        response = io.BytesIO(json.dumps({
            "ready": True,
            "backend": "kleidiai-enabled",
            "cpu_affinity": list(range(8, 16)),
            "runtime": "onnxruntime-genai",
            "runtime_version": "0.15.0.dev0",
            "architecture": "aarch64",
            "model_identity": "a" * 64,
            "source_artifact_sha256": "c" * 64,
            "runtime_lock_sha256": "d" * 64,
            "runtime_artifact_ledger_sha256": "e" * 64,
            "instance_type": "c8g.4xlarge",
            "instance_identity_source": "aws-imdsv2",
            "optimization_control": {"mlas.disable_kleidiai": "0"},
            "threads": 8,
        }).encode())
        config = {
            "endpoint": "http://127.0.0.1:8002/infer",
            "expected_backend": "kleidiai-enabled",
            "expected_cores": frozenset(range(8, 16)),
            "expected_control": "0",
        }
        with patch("scripts.serve_surgedesk.urllib.request.urlopen", return_value=response):
            verified, status, payload = _probe_lane(config)
        self.assertTrue(verified)
        self.assertIn("runtime configuration", status)
        self.assertEqual(payload["model_identity"], "a" * 64)

    def test_matched_lane_probe_rejects_a_different_model_identity(self) -> None:
        common = {
            "runtime": "onnxruntime-genai",
            "runtime_version": "0.15.0.dev0",
            "threads": 8,
            "architecture": "aarch64",
            "cpu_affinity": list(range(8)),
            "runtime_lock_sha256": "d" * 64,
            "runtime_artifact_ledger_sha256": "e" * 64,
            "instance_type": "c8g.4xlarge",
            "instance_identity_source": "aws-imdsv2",
        }
        baseline = (True, "verified", {
            **common,
            "model_identity": "a" * 64,
            "source_artifact_sha256": "c" * 64,
            "optimization_control": {"mlas.disable_kleidiai": "1"},
        })
        optimized = (True, "verified", {
            **common,
            "model_identity": "b" * 64,
            "source_artifact_sha256": "c" * 64,
            "optimization_control": {"mlas.disable_kleidiai": "0"},
        })
        matched, reason, identity = _match_lane_identity(baseline, optimized)
        self.assertFalse(matched)
        self.assertIn("identity mismatch", reason)
        self.assertEqual(identity, {})

    def test_inference_response_must_repeat_the_probed_runtime_identity(self) -> None:
        health = {
            "model_identity": "a" * 64,
            "source_artifact_sha256": "c" * 64,
            "runtime_lock_sha256": "d" * 64,
            "runtime_artifact_ledger_sha256": "e" * 64,
            "instance_type": "c8g.4xlarge",
            "instance_identity_source": "aws-imdsv2",
            "runtime": "onnxruntime-genai",
            "runtime_version": "0.15.0.dev0",
            "threads": 8,
            "architecture": "aarch64",
            "cpu_affinity": list(range(8)),
            "optimization_control": {"mlas.disable_kleidiai": "1"},
        }
        self.assertTrue(_response_identity_matches(
            {"runtime_identity": dict(health)}, health
        ))
        swapped = dict(health)
        swapped["model_identity"] = "b" * 64
        self.assertFalse(_response_identity_matches(
            {"runtime_identity": swapped}, health
        ))
        self.assertFalse(_response_identity_matches({}, health))


if __name__ == "__main__":
    unittest.main()
