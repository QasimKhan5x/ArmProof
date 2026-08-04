from __future__ import annotations

import importlib.util
import json
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "examples" / "llama-cpp-http-slo" / "bridge.py"


class _FakeLlama:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                return

            def do_POST(self) -> None:
                if self.path != "/v1/chat/completions":
                    self.send_error(404)
                    return
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                owner.requests.append(payload)
                body = json.dumps(
                    {
                        "choices": [
                            {"message": {"content": "llama.cpp compatibility works"}}
                        ],
                        "timings": {"predicted_ms": 12.5},
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
        return f"http://127.0.0.1:{self.server.server_port}/v1/chat/completions"

    def __enter__(self) -> _FakeLlama:
        self.thread.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class LlamaCppExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("llama_cpp_bridge", BRIDGE)
        assert spec and spec.loader
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_bridge_exposes_the_armproof_infer_contract(self) -> None:
        with _FakeLlama() as upstream:
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                self.module.handler_for(upstream.url, "qwen-smoke", "llama.cpp-qwen-q4"),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                payload = json.dumps(
                    {
                        "request_id": "llama-smoke-1",
                        "prompt": "Reply with a short confirmation.",
                        "max_new_tokens": 16,
                    }
                ).encode("utf-8")
                request = urllib.request.Request(
                    f"http://127.0.0.1:{server.server_port}/infer",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=2) as response:
                    result = json.load(response)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertEqual(result["request_id"], "llama-smoke-1")
        self.assertEqual(result["backend"], "llama.cpp-qwen-q4")
        self.assertEqual(result["output"], "llama.cpp compatibility works")
        self.assertEqual(upstream.requests[0]["model"], "qwen-smoke")
        self.assertEqual(upstream.requests[0]["max_tokens"], 16)
        self.assertEqual(
            upstream.requests[0]["messages"],
            [{"role": "user", "content": "Reply with a short confirmation."}],
        )


if __name__ == "__main__":
    unittest.main()
