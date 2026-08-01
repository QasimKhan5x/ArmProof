"""Verify a guest-generated SHA-256 ledger after evidence is relocated."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class ChecksumResult:
    checked: int
    missing: tuple[str, ...]
    mismatched: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.missing and not self.mismatched


def verify_checksum_ledger(
    ledger: Path,
    root: Path,
    *,
    source_prefix: str = "/opt/armproof/evidence",
) -> ChecksumResult:
    """Verify ledger entries under root while rejecting duplicates and traversal."""
    prefix = PurePosixPath(source_prefix)
    expected: dict[str, str] = {}
    for line_number, raw in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            digest, source = raw.split(maxsplit=1)
        except ValueError as exc:
            raise ValueError(f"invalid checksum line {line_number}") from exc
        source_path = PurePosixPath(source.strip())
        try:
            relative = source_path.relative_to(prefix)
        except ValueError as exc:
            raise ValueError(f"checksum path is outside source prefix: {source}") from exc
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError(f"invalid SHA-256 on line {line_number}")
        key = relative.as_posix()
        if key in expected:
            raise ValueError(f"duplicate checksum path: {key}")
        expected[key] = digest
    if not expected:
        raise ValueError("checksum ledger is empty")

    missing: list[str] = []
    mismatched: list[str] = []
    resolved_root = root.resolve()
    for relative, digest in expected.items():
        candidate = (root / relative).resolve()
        if not candidate.is_relative_to(resolved_root):
            raise ValueError(f"checksum path escapes evidence root: {relative}")
        if not candidate.is_file():
            missing.append(relative)
            continue
        with candidate.open("rb") as stream:
            observed = hashlib.file_digest(stream, "sha256").hexdigest()
        if observed != digest:
            mismatched.append(relative)
    return ChecksumResult(len(expected), tuple(missing), tuple(mismatched))
