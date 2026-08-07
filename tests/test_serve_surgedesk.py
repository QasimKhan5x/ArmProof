from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from scripts.serve_surgedesk import (
    DeploymentState,
    _match_lane_identity,
    _post_audit,
    _probe_lane,
    _response_identity_matches,
    _stream_audit,
    _upstream_request,
    handler_for,
)


class SurgeDeskGatewayTests(unittest.TestCase):
    def test_active_cutover_rejects_audit_rebinding_from_every_workflow(self) -> None:
        state = DeploymentState(
            active_lane="optimized",
            audit_experiment_id="EXP-2026-014",
            release_evidence_ids=("EXP-2026-014",),
            release_evidence_sha256={"EXP-2026-014": "b" * 64},
            audit_receipt_sha256="a" * 64,
            release_ready=True,
            promoted_at="2026-08-06T00:00:00Z",
            audited_deployment={"model_identity": "c" * 64},
            audit_workflow_id="workflow-a",
            promoted_workflow_id="workflow-a",
        )
        snapshot = state.snapshot()
        replacement = {
            "passed": True,
            "experiment_id": "EXP-replacement",
            "release_evidence_ids": ["EXP-replacement"],
            "release_evidence_sha256": {"EXP-replacement": "d" * 64},
            "receipt_sha256": "e" * 64,
            "expected_deployment_identity": {"model_identity": "f" * 64},
        }

        for workflow_id in ("workflow-a", "workflow-b"):
            with self.subTest(workflow_id=workflow_id):
                with self.assertRaisesRegex(ValueError, "active cutover"):
                    state.record_audit(replacement, workflow_id)
                with self.assertRaisesRegex(ValueError, "roll back first"):
                    state.assert_audit_allowed()
                self.assertEqual(state.snapshot(), snapshot)

    def test_optimized_authorization_requires_one_audit_and_promotion_workflow(self) -> None:
        state = DeploymentState(
            active_lane="optimized",
            audit_experiment_id="EXP-2026-014",
            release_ready=True,
            audited_deployment={"model_identity": "c" * 64},
            audit_workflow_id="workflow-b",
            promoted_workflow_id="workflow-a",
        )

        with self.assertRaisesRegex(ValueError, "active release authorization"):
            state.authorize_active_route("optimized", {"model_identity": "c" * 64})
        self.assertEqual(state.snapshot()["active_lane"], "baseline")
        self.assertFalse(state.snapshot()["release_ready"])

    def test_cutover_receipt_cannot_consume_another_workflow_comparison(self) -> None:
        state = DeploymentState(
            active_lane="optimized",
            audit_experiment_id="EXP-2026-014",
            audit_receipt_sha256="a" * 64,
            release_evidence_sha256={"EXP-2026-014": "b" * 64},
            release_ready=True,
            audit_workflow_id="workflow-a",
            promoted_workflow_id="workflow-a",
        )
        lane = {
            "request_id": "request-1",
            "input_sha256": "c" * 64,
            "model_output_sha256": "d" * 64,
            "queue": "Account security",
        }
        comparison = {
            "comparison_id": "compare-1",
            "lanes": {"baseline": lane, "optimized": {**lane, "request_id": "request-2"}},
        }
        state.record_comparison("workflow-a", comparison)
        state.record_comparison("workflow-b", {**comparison, "comparison_id": "compare-2"})
        optimized = {
            **lane,
            "request_id": "request-3",
            "runtime_identity": {"architecture": "aarch64"},
        }

        self.assertIsNone(state.issue_cutover_receipt("workflow-b", optimized))
        receipt = state.issue_cutover_receipt("workflow-a", optimized)
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["workflow_id"], "workflow-a")
        self.assertEqual(receipt["comparison_id"], "compare-1")

    def test_rollback_returns_to_baseline_and_requires_fresh_evidence(self) -> None:
        state = DeploymentState(
            active_lane="optimized",
            audit_experiment_id="EXP-2026-014",
            audit_receipt_sha256="a" * 64,
            release_evidence_ids=("EXP-2026-014",),
            release_evidence_sha256={"EXP-2026-014": "b" * 64},
            release_ready=True,
            promoted_at="2026-08-06T00:00:00Z",
            audited_deployment={"model_identity": "c" * 64},
            audit_workflow_id="workflow-a",
            promoted_workflow_id="workflow-a",
        )

        snapshot = state.rollback("workflow-a")

        self.assertEqual(snapshot["active_lane"], "baseline")
        self.assertFalse(snapshot["release_ready"])
        self.assertIsNone(snapshot["audit_experiment_id"])
        self.assertIsNone(snapshot["audit_receipt_sha256"])
        self.assertEqual(snapshot["release_evidence_ids"], [])
        with self.assertRaisesRegex(ValueError, "rollback workflow"):
            state.rollback("workflow-a")

    def test_audit_exceptions_leave_the_standard_route_blocked(self) -> None:
        class Handler:
            def __init__(self) -> None:
                self.wfile = io.BytesIO()
                self.close_connection = False

            def send_response(self, _status: int) -> None:
                return

            def send_header(self, _name: str, _value: str) -> None:
                return

            def end_headers(self) -> None:
                return

            @staticmethod
            def _body() -> dict[str, str]:
                return {"workflow_id": "workflow-test-001"}

        for audit_path in ("post", "stream"):
            with self.subTest(audit_path=audit_path):
                state = DeploymentState(
                    active_lane="baseline",
                )
                handler = Handler()
                with patch(
                    "scripts.serve_surgedesk.build_surgedesk_payload",
                    side_effect=ValueError("invalid evidence"),
                ):
                    if audit_path == "post":
                        with self.assertRaisesRegex(ValueError, "invalid evidence"):
                            _post_audit(handler, state)
                    else:
                        _stream_audit(handler, state, "workflow-test-001")
                        self.assertIn(b'"type":"error"', handler.wfile.getvalue())
                self.assertEqual(state.snapshot()["active_lane"], "baseline")
                self.assertFalse(state.snapshot()["release_ready"])

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
            "memory": {
                "baseline": {
                    "allocator": "system",
                    "transparent_huge_pages": "always",
                },
                "optimized": {
                    "allocator": "mimalloc",
                    "transparent_huge_pages": "always",
                },
            },
            "runtime_tuning": {
                "baseline": {},
                "optimized": {
                    "session.dynamic_block_base": "4",
                    "session.intra_op.spin_backoff_max": "8",
                    "session.intra_op.spin_duration_us": "1000",
                },
            },
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
            "memory": live_identity["memory"],
            "runtime_tuning": live_identity["runtime_tuning"],
        }
        workflow_id = "workflow-test-001"
        comparison = {"lanes": {"baseline": {}, "optimized": {}}}
        with self.assertRaisesRegex(ValueError, "matched comparison"):
            state.promote(live_identity, workflow_id)

        state.record_audit(
            {"passed": False, "experiment_id": "EXP-failed"}, workflow_id
        )
        with self.assertRaisesRegex(ValueError, "matched comparison"):
            state.promote(live_identity, workflow_id)

        state.record_audit({
            "passed": True,
            "experiment_id": "EXP-2026-014",
            "release_evidence_ids": ["EXP-2026-014"],
            "release_evidence_sha256": {"EXP-2026-014": "1" * 64},
            "receipt_sha256": "2" * 64,
            "expected_deployment_identity": audited,
        }, workflow_id)
        state.record_comparison(workflow_id, comparison)
        promoted = state.promote(live_identity, workflow_id)
        self.assertEqual(promoted["active_lane"], "optimized")
        self.assertEqual(promoted["audit_experiment_id"], "EXP-2026-014")
        self.assertTrue(promoted["release_ready"])
        self.assertEqual(promoted["audit_receipt_sha256"], "2" * 64)
        self.assertIsNotNone(promoted["promoted_at"])

        with self.assertRaisesRegex(ValueError, "active cutover"):
            state.record_audit(
                {"passed": False, "experiment_id": "EXP-recheck-failed"}, workflow_id
            )
        still_promoted = state.snapshot()
        self.assertEqual(still_promoted["active_lane"], "optimized")
        self.assertTrue(still_promoted["release_ready"])
        state.rollback(workflow_id)

        state.record_audit({
            "passed": True,
            "experiment_id": "EXP-2026-014",
            "release_evidence_ids": ["EXP-2026-014"],
            "release_evidence_sha256": {"EXP-2026-014": "1" * 64},
            "receipt_sha256": "2" * 64,
            "expected_deployment_identity": audited,
        }, workflow_id)
        state.record_comparison(workflow_id, comparison)
        state.promote(live_identity, workflow_id)

        state.active_lane = "baseline"
        swapped = {**live_identity, "source_artifact_sha256": "b" * 64}
        with self.assertRaisesRegex(ValueError, "differs from audited"):
            state.promote(swapped, workflow_id)
        for field, value in (
            ("model_identity", "d" * 64),
            ("runtime_lock_sha256", "e" * 64),
            ("instance_type", "c8g.8xlarge"),
            ("cpu_affinity", list(range(1, 17))),
        ):
            with self.subTest(field=field):
                state.active_lane = "baseline"
                with self.assertRaisesRegex(ValueError, "differs from audited"):
                    state.promote({**live_identity, field: value}, workflow_id)

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
                "memory_configuration": live_identity["memory"]["optimized"],
                "runtime_tuning": live_identity["runtime_tuning"]["optimized"],
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
            "memory_configuration": live_identity["memory"]["optimized"],
            "runtime_tuning": live_identity["runtime_tuning"]["optimized"],
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
            "runtime_tuning": {
                "session.dynamic_block_base": "4",
                "session.intra_op.spin_backoff_max": "8",
                "session.intra_op.spin_duration_us": "1000",
            },
            "memory_configuration": {
                "allocator": "mimalloc",
                "transparent_huge_pages": "always",
            },
            "threads": 8,
        }).encode())
        config = {
            "endpoint": "http://127.0.0.1:8002/infer",
            "expected_backend": "kleidiai-enabled",
            "expected_cores": frozenset(range(8, 16)),
            "expected_control": "0",
            "expected_memory": {
                "allocator": "mimalloc",
                "transparent_huge_pages": "always",
            },
            "expected_runtime_tuning": {
                "session.dynamic_block_base": "4",
                "session.intra_op.spin_backoff_max": "8",
                "session.intra_op.spin_duration_us": "1000",
            },
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
            "memory_configuration": {
                "allocator": "system",
                "transparent_huge_pages": "always",
            },
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
