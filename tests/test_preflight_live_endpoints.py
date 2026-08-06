from __future__ import annotations

import importlib.util
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "preflight_live_endpoints.py"


class _Endpoint:
    def __init__(self, delay_seconds: float, backend: str) -> None:
        self.delay_seconds = delay_seconds
        self.backend = backend
        self.requests: list[dict[str, object]] = []

        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                return

            def do_GET(self) -> None:
                if self.path != "/health":
                    self.send_error(404)
                    return
                control = "1" if owner.backend == "kleidiai-disabled" else "0"
                body = json.dumps({
                    "ready": True,
                    "backend": owner.backend,
                    "model_identity": "a" * 64,
                    "source_artifact_sha256": "b" * 64,
                    "runtime_lock_sha256": "c" * 64,
                    "runtime_artifact_ledger_sha256": "d" * 64,
                    "instance_type": "c8g.4xlarge",
                    "instance_identity_source": "aws-imdsv2",
                    "runtime": "onnxruntime-genai",
                    "runtime_version": "0.15.0.dev0",
                    "threads": 16,
                    "architecture": "aarch64",
                    "cpu_affinity": list(range(16)),
                    "optimization_control": {"mlas.disable_kleidiai": control},
                }).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self) -> None:
                import time

                if self.path != "/infer":
                    self.send_error(404)
                    return
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                owner.requests.append(payload)
                time.sleep(owner.delay_seconds)
                body = json.dumps(
                    {
                        "request_id": payload["request_id"],
                        "output": '{"intent":"card_arrival"}',
                        "backend": owner.backend,
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}/infer"

    def __enter__(self) -> _Endpoint:
        self.thread.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class LiveEndpointPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("preflight_live_endpoints", SCRIPT)
        assert spec and spec.loader
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_sends_the_same_request_and_reports_both_backends(self) -> None:
        with (
            _Endpoint(0.12, "kleidiai-disabled") as baseline,
            _Endpoint(0.02, "kleidiai-enabled") as optimized,
        ):
            identity = self.module.verify_live_identities(
                baseline.url, optimized.url, timeout=2
            )
            rows = self.module.compare_live_requests(
                baseline.url,
                optimized.url,
                "i have not received my card",
                ("card_arrival", "lost_or_stolen_card"),
                timeout=2,
            )

        self.assertEqual([row.label for row in rows], ["KleidiAI disabled", "KleidiAI enabled"])
        self.assertEqual(identity["source_artifact_sha256"], "b" * 64)
        self.assertEqual(rows[0].backend, "kleidiai-disabled")
        self.assertEqual(rows[1].backend, "kleidiai-enabled")
        self.assertGreater(rows[0].latency_ms, rows[1].latency_ms)
        self.assertEqual(baseline.requests[0]["prompt"], optimized.requests[0]["prompt"])
        self.assertEqual(baseline.requests[0]["max_new_tokens"], 32)
        self.assertEqual(optimized.requests[0]["max_new_tokens"], 32)

    def test_rejects_an_endpoint_that_mislabels_its_backend(self) -> None:
        with (
            _Endpoint(0.01, "kleidiai-enabled") as baseline,
            _Endpoint(0.01, "kleidiai-enabled") as optimized,
        ):
            with self.assertRaisesRegex(ValueError, "backend"):
                self.module.compare_live_requests(
                    baseline.url,
                    optimized.url,
                    "i have not received my card",
                    ("card_arrival",),
                    timeout=2,
                )


if __name__ == "__main__":
    unittest.main()
