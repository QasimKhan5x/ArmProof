"""Timestamped Linux process RSS/PSS collection."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


class MemoryError(RuntimeError):
    """Memory evidence is unavailable or malformed."""


@dataclass(frozen=True)
class MemorySample:
    timestamp_ns: int
    rss_bytes: int
    pss_bytes: int


def parse_smaps_rollup(text: str, timestamp_ns: int | None = None) -> MemorySample:
    values: dict[str, int] = {}
    for line in text.splitlines():
        if not line.startswith(("Rss:", "Pss:")):
            continue
        parts = line.split()
        if len(parts) != 3 or parts[2] != "kB":
            raise MemoryError("unexpected smaps_rollup unit or format")
        values[parts[0].removesuffix(":")] = int(parts[1]) * 1024
    if set(values) != {"Rss", "Pss"}:
        raise MemoryError("smaps_rollup did not expose RSS and PSS")
    return MemorySample(
        timestamp_ns=timestamp_ns if timestamp_ns is not None else time.monotonic_ns(),
        rss_bytes=values["Rss"],
        pss_bytes=values["Pss"],
    )


class ProcessMemorySampler:
    def __init__(
        self,
        pid: int,
        interval_seconds: float = 0.05,
        reader: Callable[[Path], str] | None = None,
    ) -> None:
        if pid <= 0 or interval_seconds <= 0:
            raise ValueError("pid and interval_seconds must be positive")
        self.path = Path(f"/proc/{pid}/smaps_rollup")
        self.interval_seconds = interval_seconds
        self.reader = reader or (lambda path: path.read_text(encoding="utf-8"))
        self._samples: list[MemorySample] = []
        self._failure: Exception | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def samples(self) -> tuple[MemorySample, ...]:
        return tuple(self._samples)

    def _capture(self) -> None:
        self._samples.append(parse_smaps_rollup(self.reader(self.path)))

    def _run(self) -> None:
        try:
            while not self._stop.wait(self.interval_seconds):
                self._capture()
        except Exception as exc:
            self._failure = exc
            self._stop.set()

    def start(self) -> None:
        if self._thread is not None:
            raise MemoryError("memory sampler is already started")
        self._capture()
        self._thread = threading.Thread(target=self._run, name="armproof-memory", daemon=True)
        self._thread.start()

    def stop(self) -> tuple[MemorySample, ...]:
        if self._thread is None:
            raise MemoryError("memory sampler is not started")
        self._stop.set()
        self._thread.join(timeout=max(1.0, self.interval_seconds * 4))
        if self._failure is None:
            try:
                self._capture()
            except Exception as exc:
                self._failure = exc
        self._thread = None
        if self._failure is not None:
            raise MemoryError(f"memory sampling failed: {self._failure}") from self._failure
        return self.samples

    def __enter__(self) -> "ProcessMemorySampler":
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.stop()
