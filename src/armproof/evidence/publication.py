"""Verify plan byte bindings and the recorded pre-measurement chronology."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Any


SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"publication {field} is not an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"publication {field} must include a timezone")
    return parsed


def _member(archive: tarfile.TarFile, name: str) -> bytes:
    try:
        member = archive.getmember(name)
    except KeyError as exc:
        raise ValueError(f"publication archive is missing {name}") from exc
    if not member.isfile():
        raise ValueError(f"publication archive member is not a file: {name}")
    stream = archive.extractfile(member)
    if stream is None:
        raise ValueError(f"publication archive member is unreadable: {name}")
    return stream.read()


def verify_preregistration_publication(
    record_path: Path,
    *,
    preregistration_path: Path,
    project_bundle_path: Path,
    evidence_archive_path: Path,
    expected_evidence_archive_sha256: str,
    repository_path: Path | None = None,
) -> dict[str, Any]:
    record = json.loads(record_path.read_text(encoding="utf-8"))
    required = {
        "schema_version", "experiment_id", "preregistration_sha256",
        "project_bundle_sha256", "evidence_archive_sha256", "git_commit",
        "git_commit_time", "instance_launch_time", "public_commit_url",
    }
    if (
        not isinstance(record, dict)
        or set(record) != required
        or record.get("schema_version") != "1.0.0"
        or not isinstance(record.get("experiment_id"), str)
        or not GIT_SHA.fullmatch(str(record.get("git_commit", "")))
        or not isinstance(record.get("public_commit_url"), str)
        or not record["public_commit_url"].endswith(record["git_commit"])
    ):
        raise ValueError("preregistration publication record is invalid")
    for field in (
        "preregistration_sha256", "project_bundle_sha256",
        "evidence_archive_sha256",
    ):
        if not SHA256.fullmatch(str(record.get(field, ""))):
            raise ValueError(f"publication {field} is invalid")

    plan_bytes = preregistration_path.read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != record["preregistration_sha256"]:
        raise ValueError("published preregistration digest does not match the plan")
    if _sha256(project_bundle_path) != record["project_bundle_sha256"]:
        raise ValueError("published project bundle digest does not match")
    archive_sha = _sha256(evidence_archive_path)
    if (
        archive_sha != record["evidence_archive_sha256"]
        or archive_sha != expected_evidence_archive_sha256
    ):
        raise ValueError("published evidence archive digest does not match")

    plan_member = f"ops/experiments/{record['experiment_id']}.json"
    with tarfile.open(project_bundle_path, "r:gz") as project:
        if _member(project, plan_member) != plan_bytes:
            raise ValueError("project bundle did not contain the published plan bytes")
    with tarfile.open(evidence_archive_path, "r:gz") as evidence:
        if _member(evidence, "evidence/experiment.json") != plan_bytes:
            raise ValueError("measurement archive did not use the published plan bytes")
        started_at = _timestamp(
            _member(evidence, "evidence/started-at.txt").decode("utf-8").strip(),
            "measurement_started_at",
        )
    commit_time = _timestamp(record["git_commit_time"], "git_commit_time")
    launch_time = _timestamp(record["instance_launch_time"], "instance_launch_time")
    git_commit_verified = False
    if repository_path is not None:
        try:
            committed_plan = subprocess.run(
                [
                    "git", "show",
                    f"{record['git_commit']}:{plan_member}",
                ],
                cwd=repository_path,
                check=True,
                capture_output=True,
                timeout=10,
            ).stdout
            committed_at = subprocess.run(
                ["git", "show", "-s", "--format=%cI", record["git_commit"]],
                cwd=repository_path,
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise ValueError("publication Git commit could not be verified locally") from exc
        if committed_plan != plan_bytes:
            raise ValueError("publication Git commit contains different plan bytes")
        if _timestamp(committed_at, "observed_git_commit_time") != commit_time:
            raise ValueError("publication Git commit time differs from the Git object")
        git_commit_verified = True
    if not commit_time < launch_time <= started_at:
        raise ValueError(
            "published plan commit, instance launch, and measurement start are out of order"
        )
    return {
        "experiment_id": record["experiment_id"],
        "preregistration_sha256": record["preregistration_sha256"],
        "git_commit": record["git_commit"],
        "git_commit_time": commit_time.isoformat(),
        "instance_launch_time": launch_time.isoformat(),
        "measurement_started_at": started_at.isoformat(),
        "public_commit_url": record["public_commit_url"],
        "git_commit_verified_in_checkout": git_commit_verified,
        "instance_launch_time_source": "recorded_experiment_metadata",
        "chronology_scope": (
            "Git commit and plan bytes verified in this checkout; instance launch "
            "time is recorded experiment metadata, not independent cloud attestation."
        ),
        "plan_embedded_in_project_bundle": True,
        "plan_embedded_in_measurement_archive": True,
    }
