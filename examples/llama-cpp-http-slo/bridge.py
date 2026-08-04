#!/usr/bin/env python3
"""Expose llama-server through ArmProof's bounded /infer request contract."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


MAX_BODY_BYTES = 64 * 1024


def _completion(payload: Any) -> tuple[str, float | None]:
    if not isinstance(payload, dict):
        raise ValueError("llama.cpp response must be an object")
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise ValueError("llama.cpp response must contain one choice")
    choice = choices[0]
    message = choice.get("message") if isinstance(choice, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise ValueError("llama.cpp response has no text content")
    timings = payload.get("timings")
    predicted_ms = timings.get("predicted_ms") if isinstance(timings, dict) else None
    return content, float(predicted_ms) if isinstance(predicted_ms, (int, float)) else None


def handler_for(
    llama_url: str,
    model: str,
    backend_label: str,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path != "/health":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            self._json(HTTPStatus.OK, {"status": "ok", "backend": backend_label})

        def do_POST(self) -> None:
            if self.path != "/infer":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY_BYTES:
                    raise ValueError("invalid request size")
                incoming = json.loads(self.rfile.read(length))
                if not isinstance(incoming, dict) or set(incoming) != {
                    "request_id", "prompt", "max_new_tokens"
                }:
                    raise ValueError("request requires request_id, prompt and max_new_tokens")
                request_id = incoming["request_id"]
                prompt = incoming["prompt"]
                max_tokens = incoming["max_new_tokens"]
                if not isinstance(request_id, str) or not request_id:
                    raise ValueError("request_id must be non-empty")
                if not isinstance(prompt, str) or not 1 <= len(prompt) <= 32_000:
                    raise ValueError("prompt must contain 1 to 32000 characters")
                if not isinstance(max_tokens, int) or not 1 <= max_tokens <= 512:
                    raise ValueError("max_new_tokens must be between 1 and 512")
                body = json.dumps(
                    {
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": 0,
                        "stream": False,
                    },
                    separators=(",", ":"),
                ).encode("utf-8")
                request = urllib.request.Request(
                    llama_url,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=120) as response:
                    output, inference_ms = _completion(json.load(response))
                result: dict[str, object] = {
                    "request_id": request_id,
                    "output": output,
                    "backend": backend_label,
                }
                if inference_ms is not None:
                    result["inference_ms"] = inference_ms
                self._json(HTTPStatus.OK, result)
            except (json.JSONDecodeError, ValueError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except (OSError, urllib.error.URLError, TimeoutError) as exc:
                self._json(HTTPStatus.BAD_GATEWAY, {"error": type(exc).__name__})

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llama-url", default="http://127.0.0.1:8080/v1/chat/completions")
    parser.add_argument("--model", required=True, help="llama-server model alias")
    parser.add_argument("--backend-label", default="llama.cpp")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    ThreadingHTTPServer(
        (args.host, args.port),
        handler_for(args.llama_url, args.model, args.backend_label),
    ).serve_forever()


if __name__ == "__main__":
    main()
