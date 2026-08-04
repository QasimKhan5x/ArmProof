from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from scripts.serve_surgedesk import (
    _match_lane_identity,
    _probe_lane,
    _response_identity_matches,
    _upstream_request,
    handler_for,
)


class SurgeDeskGatewayTests(unittest.TestCase):
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

    def test_matched_endpoints_require_distinct_urls_and_equal_disjoint_cores(self) -> None:
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
        with self.assertRaisesRegex(ValueError, "disjoint"):
            handler_for(
                baseline_endpoint="http://baseline/infer",
                optimized_endpoint="http://optimized/infer",
                baseline_cores="0-7",
                optimized_cores="7-14",
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
        }
        baseline = (True, "verified", {
            **common,
            "model_identity": "a" * 64,
            "optimization_control": {"mlas.disable_kleidiai": "1"},
        })
        optimized = (True, "verified", {
            **common,
            "model_identity": "b" * 64,
            "optimization_control": {"mlas.disable_kleidiai": "0"},
        })
        matched, reason, identity = _match_lane_identity(baseline, optimized)
        self.assertFalse(matched)
        self.assertIn("identity mismatch", reason)
        self.assertEqual(identity, {})

    def test_inference_response_must_repeat_the_probed_runtime_identity(self) -> None:
        health = {
            "model_identity": "a" * 64,
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
