#!/usr/bin/env python3
"""Serve SurgeDesk and optionally proxy a trusted Arm inference endpoint."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from armproof.demo.live import build_prompt, compose_live_route  # noqa: E402
from armproof.demo.surgedesk import _queue_guard  # noqa: E402


MAX_BODY_BYTES = 16 * 1024


def handler_for(endpoint: str | None) -> type[SimpleHTTPRequestHandler]:
    guard, _ = _queue_guard(ROOT)
    categories = json.loads(
        (ROOT / "data/banking77/source/categories.json").read_text(encoding="utf-8")
    )

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(ROOT), **kwargs)

        def _json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/surgedesk/live-status.json":
                self._json(
                    HTTPStatus.OK,
                    {"live_available": bool(endpoint), "mode": "live" if endpoint else "recorded"},
                )
                return
            super().do_GET()

        def do_POST(self) -> None:
            if self.path != "/api/route":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            if not endpoint:
                self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "live_endpoint_not_configured"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY_BYTES:
                    raise ValueError("invalid request size")
                payload = json.loads(self.rfile.read(length))
                text = payload.get("text") if isinstance(payload, dict) else None
                if not isinstance(text, str) or not 1 <= len(text.strip()) <= 4000:
                    raise ValueError("text must contain 1 to 4000 characters")
                request_payload = json.dumps(
                    {
                        "request_id": f"surgedesk-{uuid.uuid4().hex[:12]}",
                        "prompt": build_prompt(text.strip(), categories),
                        "max_new_tokens": 32,
                    }
                ).encode("utf-8")
                request = urllib.request.Request(
                    endpoint,
                    data=request_payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=60) as response:
                    upstream = json.load(response)
                self._json(
                    HTTPStatus.OK,
                    compose_live_route(text.strip(), upstream, guard, categories),
                )
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except (urllib.error.URLError, TimeoutError) as exc:
                self._json(HTTPStatus.BAD_GATEWAY, {"error": type(exc).__name__})

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--endpoint", default=os.environ.get("SURGEDESK_INFERENCE_ENDPOINT"))
    args = parser.parse_args()
    print(f"SurgeDesk: http://{args.host}:{args.port}/surgedesk/")
    print(f"Live inference: {'enabled' if args.endpoint else 'disabled'}")
    ThreadingHTTPServer((args.host, args.port), handler_for(args.endpoint)).serve_forever()


if __name__ == "__main__":
    main()
