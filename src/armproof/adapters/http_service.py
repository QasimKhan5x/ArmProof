"""Managed subprocess exposing the common ArmProof HTTP treatment interface."""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class ServiceError(RuntimeError):
    """Treatment process did not satisfy its lifecycle contract."""


@dataclass(frozen=True)
class ServiceSpec:
    treatment_id: str
    command: tuple[str, ...]
    environment: Mapping[str, str]
    health_url: str
    request_url: str
    log_path: Path
    startup_timeout_seconds: float = 60.0
    request_timeout_seconds: float = 30.0
    shutdown_timeout_seconds: float = 10.0
    cwd: Path | None = None

    def __post_init__(self) -> None:
        if not self.treatment_id:
            raise ValueError("treatment_id must be non-empty")
        if not self.command or not all(isinstance(item, str) and item for item in self.command):
            raise ValueError("command must be a non-empty string tuple")
        if self.startup_timeout_seconds <= 0 or self.request_timeout_seconds <= 0:
            raise ValueError("timeouts must be positive")


class ManagedHttpService:
    def __init__(self, spec: ServiceSpec) -> None:
        self.spec = spec
        self._process: subprocess.Popen[bytes] | None = None
        self._log = None

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process is not None else None

    def start(self) -> None:
        if self._process is not None:
            raise ServiceError("service is already started")
        self.spec.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = self.spec.log_path.open("ab")
        environment = os.environ.copy()
        environment.update(self.spec.environment)
        try:
            self._process = subprocess.Popen(
                list(self.spec.command),
                cwd=self.spec.cwd,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=self._log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            self._wait_until_ready()
        except Exception:
            self.stop()
            raise

    def _wait_until_ready(self) -> None:
        deadline = time.monotonic() + self.spec.startup_timeout_seconds
        while time.monotonic() < deadline:
            assert self._process is not None
            return_code = self._process.poll()
            if return_code is not None:
                raise ServiceError(f"service exited before readiness with code {return_code}")
            try:
                with urllib.request.urlopen(self.spec.health_url, timeout=0.5) as response:
                    if 200 <= response.status < 300:
                        return
            except (OSError, urllib.error.URLError):
                time.sleep(0.05)
        raise ServiceError("service readiness timed out")

    def request(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if self._process is None or self._process.poll() is not None:
            raise ServiceError("service is not running")
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            self.spec.request_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.spec.request_timeout_seconds) as response:
                parsed = json.loads(response.read())
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise ServiceError(f"request failed: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ServiceError("service response must be a JSON object")
        return parsed

    def stop(self) -> None:
        process = self._process
        self._process = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=self.spec.shutdown_timeout_seconds)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        if self._log is not None:
            self._log.close()
            self._log = None

    def __enter__(self) -> "ManagedHttpService":
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.stop()

