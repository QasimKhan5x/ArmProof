"""Deterministic evidence manifests with explicit historical decisions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


class ManifestError(ValueError):
    """Evidence cannot be represented without violating its history."""


EXPECTED_DECISIONS = {
    "EXP-2026-001": False,
    "EXP-2026-002": True,
}


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decision(evidence_root: Path, experiment_id: str) -> str:
    summary_path = evidence_root / experiment_id / "summary.json"
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot read {summary_path}: {exc}") from exc
    passed = summary.get("passed")
    expected = EXPECTED_DECISIONS[experiment_id]
    if passed is not expected:
        required = "passed" if expected else "failed"
        raise ManifestError(f"{experiment_id} must remain {required}")
    return "passed" if passed else "failed"


def build_manifest(
    evidence_root: Path,
    source_archives: Mapping[str, Path],
) -> dict[str, Any]:
    """Build a stable manifest without mutating or recasting source evidence."""
    evidence_root = evidence_root.resolve()
    experiments = [
        {"experiment_id": experiment_id, "decision": _decision(evidence_root, experiment_id)}
        for experiment_id in sorted(EXPECTED_DECISIONS)
    ]
    files = []
    for path in sorted(evidence_root.rglob("*")):
        if not path.is_file() or path.name == "manifest.json" or "large" in path.parts:
            continue
        files.append(
            {
                "path": path.relative_to(evidence_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    archives = []
    for experiment_id, path in sorted(source_archives.items()):
        if experiment_id not in EXPECTED_DECISIONS:
            raise ManifestError(f"unknown source experiment: {experiment_id}")
        if not path.is_file():
            raise ManifestError(f"source archive does not exist: {path}")
        archives.append(
            {
                "experiment_id": experiment_id,
                "filename": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "retention": "external-local-source",
                "omitted_payloads": [
                    "build artifacts",
                    "binary perf recordings",
                ],
            }
        )
    redactions = []
    if (evidence_root / "source-records/spend-ledger.json").is_file():
        redactions.append(
            {
                "path": "source-records/spend-ledger.json",
                "field": "instance_id",
                "reason": "public-copy machine identifier",
            }
        )
    return {
        "schema_version": "1.0.0",
        "bundle_id": "imported-migration-measurements",
        "redactions": redactions,
        "experiments": experiments,
        "files": files,
        "source_archives": archives,
    }


def verify_manifest(evidence_root: Path, manifest: Mapping[str, Any]) -> list[str]:
    """Return every missing, size-mismatched, or hash-mismatched file."""
    errors: list[str] = []
    evidence_root = evidence_root.resolve()
    for record in manifest.get("files", []):
        relative = record.get("path")
        if not isinstance(relative, str):
            errors.append("manifest file record has no path")
            continue
        path = (evidence_root / relative).resolve()
        try:
            path.relative_to(evidence_root)
        except ValueError:
            errors.append(f"path escapes evidence root: {relative}")
            continue
        if not path.is_file():
            errors.append(f"missing file: {relative}")
            continue
        if path.stat().st_size != record.get("bytes"):
            errors.append(f"size mismatch: {relative}")
            continue
        if sha256_file(path) != record.get("sha256"):
            errors.append(f"sha256 mismatch: {relative}")
    return errors
