"""Run identity-bearing test lanes behind the real SurgeDesk gateway."""

from __future__ import annotations

import json
import os
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from scripts.serve_surgedesk import handler_for


SOURCE_SHA = "9ef697ababdc0b4ffc63b098bbd4760f79795eb0502ca4d41c80e20843ac0ab1"


def lane_handler(backend: str, control: str) -> type[BaseHTTPRequestHandler]:
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

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *args: object) -> None:
            return

        def respond(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/health":
                self.respond(HTTPStatus.OK, {"ready": True, "backend": backend, **identity})
            else:
                self.respond(HTTPStatus.NOT_FOUND, {"error": "not_found"})

        def do_POST(self) -> None:
            if self.path != "/infer":
                self.respond(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            prompt = str(request.get("prompt", "")).lower()
            intent = (
                "card_about_to_expire"
                if "about to expire" in prompt
                else "lost_or_stolen_card"
            )
            self.respond(HTTPStatus.OK, {
                "request_id": request["request_id"],
                "backend": backend,
                "output": json.dumps({"intent": intent}),
                "inference_ms": 3.0,
                "runtime_identity": identity,
            })

    return Handler


def main() -> None:
    baseline = ThreadingHTTPServer(
        ("127.0.0.1", 0), lane_handler("kleidiai-disabled", "1")
    )
    optimized = ThreadingHTTPServer(
        ("127.0.0.1", 0), lane_handler("kleidiai-enabled", "0")
    )
    gateway = ThreadingHTTPServer(
        ("127.0.0.1", int(os.environ.get("SURGEDESK_TEST_PORT", "8876"))),
        handler_for(
            baseline_endpoint=f"http://127.0.0.1:{baseline.server_port}/infer",
            optimized_endpoint=f"http://127.0.0.1:{optimized.server_port}/infer",
            baseline_cores="0-15",
            optimized_cores="0-15",
        ),
    )
    for server in (baseline, optimized):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        gateway.serve_forever()
    finally:
        gateway.server_close()
        baseline.shutdown()
        optimized.shutdown()
        baseline.server_close()
        optimized.server_close()


if __name__ == "__main__":
    main()
