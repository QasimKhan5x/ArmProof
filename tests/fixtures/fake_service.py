from __future__ import annotations

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    backend = "fake"
    fixed_delay_ms = 0.0

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_POST(self) -> None:
        if self.path != "/infer":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        time.sleep((self.fixed_delay_ms + float(payload.get("delay_ms", 0))) / 1000)
        body = json.dumps({
            "request_id": payload["request_id"],
            "output": '{"intent":"card_arrival"}',
            "backend": self.backend,
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--backend", default="fake")
    parser.add_argument("--delay-ms", type=float, default=0.0)
    args = parser.parse_args()
    Handler.backend = args.backend
    Handler.fixed_delay_ms = args.delay_ms
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
