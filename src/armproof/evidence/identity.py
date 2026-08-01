"""Deterministic file and directory artifact identity."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from armproof.evidence.manifest import sha256_file


@dataclass(frozen=True)
class ArtifactFingerprint:
    kind: str
    bytes: int
    files: int
    sha256: str


def fingerprint_path(path: Path) -> ArtifactFingerprint:
    if path.is_file():
        return ArtifactFingerprint("file", path.stat().st_size, 1, sha256_file(path))
    if not path.is_dir():
        raise FileNotFoundError(path)
    digest = hashlib.sha256()
    digest.update(b"armproof-directory-v1\0")
    total_bytes = 0
    files = 0
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        relative = item.relative_to(path).as_posix().encode("utf-8")
        size = item.stat().st_size
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(size.to_bytes(8, "big"))
        digest.update(bytes.fromhex(sha256_file(item)))
        total_bytes += size
        files += 1
    return ArtifactFingerprint("directory", total_bytes, files, digest.hexdigest())
