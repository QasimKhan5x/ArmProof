from __future__ import annotations

import hashlib
import json
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import ExitStack, contextmanager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator

from scripts.serve_surgedesk import handler_for


SOURCE_SHA = "9ef697ababdc0b4ffc63b098bbd4760f79795eb0502ca4d41c80e20843ac0ab1"
RUNTIME_LOCK_SHA = "68a4aa0e9b52bfacd435b1515aa5cc34acb760ba63961ddf70f6b0b01c96a884"
MODEL_SHA = "d86ae7ca1f12b2ae4abe70abb856cb9c688908477a7de653467623764ab5c687"
WORKFLOW_ID = "workflow-e2e-001"


def _lane_handler(
    backend: str,
    control: str,
) -> tuple[type[BaseHTTPRequestHandler], dict[str, Any]]:
    allocator = "system" if control == "1" else "mimalloc"
    runtime_tuning = {} if control == "1" else {
        "session.dynamic_block_base": "4",
        "session.intra_op.spin_backoff_max": "8",
        "session.intra_op.spin_duration_us": "1000",
    }
    identity = {
        "model_identity": MODEL_SHA,
        "source_artifact_sha256": SOURCE_SHA,
        "runtime_lock_sha256": RUNTIME_LOCK_SHA,
        "runtime_artifact_ledger_sha256": "2ac3491c5ce6d6b1dc178f27568b1e6e66b9b76031bc488143e72d9e7488d8c7",
        "instance_type": "c8g.4xlarge",
        "instance_identity_source": "aws-imdsv2",
        "runtime": "onnxruntime-genai",
        "runtime_version": "0.15.0.dev0",
        "threads": 16,
        "architecture": "aarch64",
        "cpu_affinity": list(range(16)),
        "optimization_control": {"mlas.disable_kleidiai": control},
        "memory_configuration": {
            "allocator": allocator,
            "transparent_huge_pages": "always",
        },
        "runtime_tuning": runtime_tuning,
    }

    class LaneHandler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *args: object) -> None:
            return

        def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path != "/health":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            self._json(HTTPStatus.OK, {"ready": True, "backend": backend, **identity})

        def do_POST(self) -> None:
            if self.path != "/infer":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self._json(HTTPStatus.OK, {
                "request_id": request["request_id"],
                "backend": backend,
                "output": '{"intent":"lost_or_stolen_card"}',
                "inference_ms": 3.0,
                "runtime_identity": identity,
            })

    return LaneHandler, identity


@contextmanager
def _server(handler: type[BaseHTTPRequestHandler]) -> Iterator[ThreadingHTTPServer]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _request(url: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request_payload = dict(payload or {})
    if path.startswith("/api/"):
        request_payload.setdefault("workflow_id", WORKFLOW_ID)
    body = json.dumps(request_payload).encode()
    request = urllib.request.Request(
        f"{url}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)


class SurgeDeskGatewayEndToEndTests(unittest.TestCase):
    def test_real_http_flow_routes_control_then_audited_treatment(self) -> None:
        with ExitStack() as stack:
            baseline_handler, _ = _lane_handler("kleidiai-disabled", "1")
            optimized_handler, optimized_identity = _lane_handler("kleidiai-enabled", "0")
            baseline = stack.enter_context(_server(baseline_handler))
            optimized = stack.enter_context(_server(optimized_handler))
            gateway_handler = handler_for(
                baseline_endpoint=f"http://127.0.0.1:{baseline.server_port}/infer",
                optimized_endpoint=f"http://127.0.0.1:{optimized.server_port}/infer",
                baseline_cores="0-15",
                optimized_cores="0-15",
            )
            gateway = stack.enter_context(_server(gateway_handler))
            root = f"http://127.0.0.1:{gateway.server_port}"

            message = "My card was stolen while I am travelling"
            comparison = _request(root, "/api/shadow-compare", {"text": message})
            self.assertEqual(comparison["execution"], "sequential_shadow")
            self.assertEqual(comparison["serving_lane"], "baseline")
            self.assertEqual(comparison["lanes"]["baseline"]["deployment_lane"], "baseline")
            self.assertEqual(comparison["lanes"]["optimized"]["deployment_lane"], "optimized")
            self.assertTrue(comparison["lanes"]["optimized"]["shadow_only"])
            self.assertTrue(comparison["same_queue"])
            self.assertFalse(comparison["capacity_evidence"])

            first = _request(root, "/api/route", {"text": message})
            self.assertEqual(first["backend"], "kleidiai-disabled")
            self.assertEqual(first["deployment_lane"], "baseline")
            self.assertIsNone(first["release_audit_id"])
            self.assertEqual(first["runtime_identity"]["architecture"], "aarch64")
            self.assertEqual(
                first["runtime_identity"]["optimization_control"][
                    "mlas.disable_kleidiai"
                ],
                "1",
            )
            self.assertIn("observed_at", first)

            receipt = _request(root, "/api/audit")
            self.assertTrue(receipt["passed"])
            self.assertEqual(receipt["workflow_id"], WORKFLOW_ID)
            self.assertEqual(len(receipt["release_evidence_sha256"]), 7)
            self.assertEqual(len(receipt["receipt_sha256"]), 64)
            promoted = _request(root, "/api/promote")
            self.assertEqual(promoted["active_lane"], "optimized")
            self.assertEqual(promoted["runtime_identity"]["source_artifact_sha256"], SOURCE_SHA)

            second = _request(root, "/api/route", {"text": message})
            self.assertEqual(second["backend"], "kleidiai-enabled")
            self.assertEqual(second["deployment_lane"], "optimized")
            self.assertEqual(second["release_audit_id"], receipt["experiment_id"])
            self.assertEqual(second["release_evidence_sha256"], receipt["release_evidence_sha256"])
            self.assertEqual(second["audit_receipt_sha256"], receipt["receipt_sha256"])
            cutover = second["cutover_receipt"]
            self.assertEqual(cutover["workflow_id"], WORKFLOW_ID)
            self.assertEqual(cutover["comparison_id"], comparison["comparison_id"])
            self.assertEqual(
                cutover["before"]["request_id"],
                comparison["lanes"]["baseline"]["request_id"],
            )
            self.assertEqual(
                cutover["before"]["input_sha256"],
                comparison["lanes"]["baseline"]["input_sha256"],
            )
            self.assertEqual(cutover["after"]["request_id"], second["request_id"])
            self.assertEqual(cutover["after"]["input_sha256"], second["input_sha256"])
            self.assertEqual(
                cutover["release"]["audit_receipt_sha256"], receipt["receipt_sha256"]
            )
            self.assertEqual(
                cutover["release"]["evidence_sha256"],
                receipt["release_evidence_sha256"],
            )
            self.assertEqual(
                json.loads(cutover["canonical_body"])["comparison_id"],
                comparison["comparison_id"],
            )
            self.assertEqual(
                hashlib.sha256(cutover["canonical_body"].encode()).hexdigest(),
                cutover["receipt_sha256"],
            )
            self.assertEqual(len(cutover["receipt_sha256"]), 64)
            self.assertEqual(
                second["runtime_identity"]["optimization_control"][
                    "mlas.disable_kleidiai"
                ],
                "0",
            )

            optimized_identity["model_identity"] = "f" * 64
            with self.assertRaises(urllib.error.HTTPError) as context:
                _request(root, "/api/route", {"text": message})
            self.assertEqual(context.exception.code, HTTPStatus.CONFLICT)
            status = _request(root, "/api/route", {"text": message})
            self.assertEqual(status["deployment_lane"], "baseline")
            self.assertIsNone(status["release_audit_id"])

            optimized_identity["model_identity"] = MODEL_SHA
            _request(root, "/api/shadow-compare", {"text": message})
            receipt = _request(root, "/api/audit")
            self.assertTrue(receipt["passed"])
            self.assertEqual(_request(root, "/api/promote")["active_lane"], "optimized")
            optimized_identity["architecture"] = "x86_64"
            with self.assertRaises(urllib.error.HTTPError) as context:
                _request(root, "/api/route", {"text": message})
            self.assertEqual(context.exception.code, HTTPStatus.CONFLICT)
            optimized_identity["architecture"] = "aarch64"
            status = _request(root, "/api/route", {"text": message})
            self.assertEqual(status["deployment_lane"], "baseline")
            self.assertIsNone(status["release_audit_id"])


if __name__ == "__main__":
    unittest.main()
