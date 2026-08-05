from __future__ import annotations

import json
import threading
import unittest
import urllib.request
from contextlib import ExitStack, contextmanager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator

from scripts.serve_surgedesk import handler_for


SOURCE_SHA = "9ef697ababdc0b4ffc63b098bbd4760f79795eb0502ca4d41c80e20843ac0ab1"


def _lane_handler(backend: str, control: str) -> type[BaseHTTPRequestHandler]:
    identity = {
        "model_identity": "a" * 64,
        "source_artifact_sha256": SOURCE_SHA,
        "runtime": "onnxruntime-genai",
        "runtime_version": "0.15.0.dev0",
        "threads": 16,
        "architecture": "aarch64",
        "cpu_affinity": list(range(16)),
        "optimization_control": {"mlas.disable_kleidiai": control},
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

    return LaneHandler


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
    body = json.dumps(payload).encode() if payload is not None else b""
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
            baseline = stack.enter_context(
                _server(_lane_handler("kleidiai-disabled", "1"))
            )
            optimized = stack.enter_context(
                _server(_lane_handler("kleidiai-enabled", "0"))
            )
            gateway_handler = handler_for(
                baseline_endpoint=f"http://127.0.0.1:{baseline.server_port}/infer",
                optimized_endpoint=f"http://127.0.0.1:{optimized.server_port}/infer",
                baseline_cores="0-15",
                optimized_cores="0-15",
            )
            gateway = stack.enter_context(_server(gateway_handler))
            root = f"http://127.0.0.1:{gateway.server_port}"

            message = "My card was stolen while I am travelling"
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
            promoted = _request(root, "/api/promote")
            self.assertEqual(promoted["active_lane"], "optimized")
            self.assertEqual(promoted["runtime_identity"]["source_artifact_sha256"], SOURCE_SHA)

            second = _request(root, "/api/route", {"text": message})
            self.assertEqual(second["backend"], "kleidiai-enabled")
            self.assertEqual(second["deployment_lane"], "optimized")
            self.assertEqual(second["release_audit_id"], receipt["experiment_id"])
            self.assertEqual(
                second["runtime_identity"]["optimization_control"][
                    "mlas.disable_kleidiai"
                ],
                "0",
            )


if __name__ == "__main__":
    unittest.main()
