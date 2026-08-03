from __future__ import annotations

import os
import socket
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

from armproof.adapters import (
    ExclusiveHttpServicePool,
    ManagedHttpService,
    ServiceError,
    ServiceSpec,
)


ROOT = Path(__file__).resolve().parents[2]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ManagedHttpServiceTests(unittest.TestCase):
    def test_exclusive_pool_stops_every_peer_before_starting_selected(self) -> None:
        first = ManagedHttpService(ServiceSpec(
            "first", ("python", "first.py"), {}, "http://one/health",
            "http://one/infer", Path("first.log"),
        ))
        second = ManagedHttpService(ServiceSpec(
            "second", ("python", "second.py"), {}, "http://two/health",
            "http://two/infer", Path("second.log"),
        ))
        events = []
        with (
            patch.object(first, "stop", side_effect=lambda: events.append("stop-first")),
            patch.object(second, "stop", side_effect=lambda: events.append("stop-second")),
            patch.object(second, "start", side_effect=lambda: events.append("start-second")),
        ):
            selected = ExclusiveHttpServicePool((first, second)).activate("second")
        self.assertIs(selected, second)
        self.assertEqual(events, ["stop-first", "stop-second", "start-second"])

    def test_restart_stops_then_starts_service(self) -> None:
        spec = ServiceSpec(
            treatment_id="test",
            command=("python", "service.py"),
            environment={},
            health_url="http://127.0.0.1:8000/health",
            request_url="http://127.0.0.1:8000/infer",
            log_path=Path("service.log"),
        )
        service = ManagedHttpService(spec)
        with patch.object(service, "stop") as stop, patch.object(service, "start") as start:
            service.restart()
        stop.assert_called_once_with()
        start.assert_called_once_with()

    def test_lifecycle_and_request_contract(self) -> None:
        class Response:
            status = 200

            def __init__(self, body: bytes) -> None:
                self.body = BytesIO(body)

            def read(self) -> bytes:
                return self.body.read()

            def __enter__(self) -> "Response":
                return self

            def __exit__(self, *args: object) -> None:
                return None

        process = Mock()
        process.pid = 1234
        process.poll.return_value = None
        process.wait.return_value = 0
        spec = ServiceSpec(
            treatment_id="fixture",
            command=("serve",),
            environment={},
            health_url="http://127.0.0.1:1/health",
            request_url="http://127.0.0.1:1/infer",
            startup_timeout_seconds=1.0,
            log_path=Path(tempfile.gettempdir()) / "armproof-adapter-test.log",
        )
        with (
            patch("armproof.adapters.http_service.subprocess.Popen", return_value=process),
            patch(
                "armproof.adapters.http_service.urllib.request.urlopen",
                side_effect=[Response(b"ok"), Response(b'{"request_id":"r1"}')],
            ),
        ):
            service = ManagedHttpService(spec)
            with service:
                self.assertEqual(service.request({"request_id": "r1"})["request_id"], "r1")
                self.assertEqual(service.pid, 1234)
            self.assertIsNone(service.pid)
        process.terminate.assert_called_once()

    @unittest.skipUnless(
        os.environ.get("ARMPROOF_NETWORK_TESTS") == "1",
        "requires localhost TCP connectivity",
    )
    def test_process_readiness_request_and_shutdown(self) -> None:
        port = free_port()
        with tempfile.TemporaryDirectory() as temporary:
            spec = ServiceSpec(
                treatment_id="fixture",
                command=(
                    sys.executable,
                    str(ROOT / "tests/fixtures/fake_service.py"),
                    "--port",
                    str(port),
                ),
                environment={},
                health_url=f"http://127.0.0.1:{port}/health",
                request_url=f"http://127.0.0.1:{port}/infer",
                startup_timeout_seconds=3.0,
                request_timeout_seconds=1.0,
                log_path=Path(temporary) / "service.log",
            )
            service = ManagedHttpService(spec)
            try:
                with service:
                    response = service.request({"request_id": "r1"})
                    self.assertEqual(response["request_id"], "r1")
                    self.assertIsNotNone(service.pid)
            except ServiceError as exc:
                log = spec.log_path.read_text(errors="replace") if spec.log_path.exists() else "<missing>"
                self.fail(f"{exc}; service log: {log}")
            self.assertIsNone(service.pid)

    def test_empty_command_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "command"):
            ServiceSpec(
                treatment_id="bad",
                command=(),
                environment={},
                health_url="http://127.0.0.1/health",
                request_url="http://127.0.0.1/infer",
                log_path=Path("bad.log"),
            )


if __name__ == "__main__":
    unittest.main()
