"""Small, fail-closed helpers for native Arm Performix run evidence."""

from __future__ import annotations

import json
import csv
import hashlib
import io
import math
import tarfile
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from collections.abc import Iterator
from pathlib import Path
from typing import Any


PERFORMIX_CONFIG_FIELDS = {
    "archive",
    "archive_sha256",
    "experiment_id",
    "disabled_run_id",
    "enabled_run_id",
    "linux_perf_kai_cycle_share",
    "maximum_share_difference",
}


def _objects(text: str) -> Iterator[dict[str, Any]]:
    decoder = json.JSONDecoder()
    offset = 0
    while offset < len(text):
        start = text.find("{", offset)
        if start < 0:
            return
        try:
            value, consumed = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            offset = start + 1
            continue
        offset = start + consumed
        if isinstance(value, dict):
            yield value


def _run_ids(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"run_id", "runId", "RunId"}:
                if isinstance(child, str) and child:
                    yield child
                elif isinstance(child, dict):
                    identifier = child.get("value")
                    if isinstance(identifier, str) and identifier:
                        yield identifier
            yield from _run_ids(child)
    elif isinstance(value, list):
        for child in value:
            yield from _run_ids(child)


def extract_run_id(output: str) -> str:
    """Return the final run ID from streamed APX JSON or fail closed."""
    identifiers = [identifier for obj in _objects(output) for identifier in _run_ids(obj)]
    if not identifiers:
        raise ValueError("Performix output contains no run_id")
    if len(set(identifiers)) != 1:
        raise ValueError(f"Performix output contains conflicting run IDs: {identifiers}")
    return identifiers[-1]


@dataclass(frozen=True)
class HotspotEvidence:
    run_id: str
    command: str
    engine_version: str
    cpu_names: tuple[str, ...]
    total_function_samples: int
    kai_function_samples: int
    kai_sample_share: float
    kai_symbols: tuple[str, ...]


def read_code_hotspots_export(path: Path) -> HotspotEvidence:
    """Read measured function samples from one native Performix export."""
    try:
        with zipfile.ZipFile(path) as archive:
            roots = {
                name.split("/", 1)[0]
                for name in archive.namelist()
                if "/" in name
            }
            if len(roots) != 1:
                raise ValueError("Performix export must contain exactly one run root")
            run_id = roots.pop()
            metadata = json.loads(archive.read(f"{run_id}/metadata.json"))
            if metadata.get("run.recipe_name") != "code_hotspots":
                raise ValueError("Performix export is not a Code Hotspots run")
            if metadata.get("run.result") != "success" or metadata.get("run.error"):
                raise ValueError(
                    "Performix Code Hotspots run did not complete successfully"
                )
            function_path = (
                f"{run_id}/tool/neoprof/0/output/"
                "functions-capture-periodic_sampling.csv"
            )
            rows = csv.DictReader(
                io.StringIO(archive.read(function_path).decode("utf-8"))
            )
            total = 0
            kai_total = 0
            symbols: set[str] = set()
            for row in rows:
                samples = int(row["Periodic Samples"])
                symbol = row["symbol"]
                if samples < 0:
                    raise ValueError(
                        "Performix function sample count cannot be negative"
                    )
                total += samples
                if symbol.startswith("kai_"):
                    kai_total += samples
                    symbols.add(symbol)
            if total <= 0:
                raise ValueError(
                    "Performix export contains no measured function samples"
                )
            cpu_path = (
                f"{run_id}/collector/sl-collect-target-info/"
                "sl-collect-target-info-cpus.json"
            )
            cpus = json.loads(archive.read(cpu_path))
            cpu_names = tuple(sorted({str(cpu["name"]) for cpu in cpus}))
            return HotspotEvidence(
                run_id=run_id,
                command=str(metadata["run.workload.cmdline"]),
                engine_version=str(metadata["engine.version"]),
                cpu_names=cpu_names,
                total_function_samples=total,
                kai_function_samples=kai_total,
                kai_sample_share=kai_total / total,
                kai_symbols=tuple(sorted(symbols)),
            )
    except (
        csv.Error,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        UnicodeDecodeError,
        zipfile.BadZipFile,
    ) as exc:
        raise ValueError(f"malformed Performix Code Hotspots export: {path}") from exc


def compare_code_hotspots(
    disabled_path: Path,
    enabled_path: Path,
    *,
    linux_perf_share: float,
    maximum_share_difference: float,
) -> dict[str, Any]:
    """Validate the matched Performix control and independent attribution."""
    if (
        not math.isfinite(linux_perf_share)
        or not 0 <= linux_perf_share <= 1
        or not math.isfinite(maximum_share_difference)
        or not 0 <= maximum_share_difference <= 1
    ):
        raise ValueError("Performix comparison shares must be finite values from 0 to 1")
    disabled = read_code_hotspots_export(disabled_path)
    enabled = read_code_hotspots_export(enabled_path)
    if disabled.engine_version != enabled.engine_version:
        raise ValueError("Performix engine versions do not match")
    if disabled.cpu_names != enabled.cpu_names or not disabled.cpu_names:
        raise ValueError("Performix target CPU identities do not match")
    normalized_disabled = disabled.command.replace("kleidiai-disabled", "TREATMENT")
    normalized_enabled = enabled.command.replace("kleidiai-enabled", "TREATMENT")
    if normalized_disabled != normalized_enabled:
        raise ValueError("Performix workload commands differ beyond treatment overlay")
    if disabled.kai_function_samples != 0:
        raise ValueError("disabled Performix control contains measured kai_* samples")
    if enabled.kai_function_samples <= 0:
        raise ValueError("enabled Performix treatment contains no measured kai_* samples")
    difference = abs(enabled.kai_sample_share - linux_perf_share)
    if difference > maximum_share_difference:
        raise ValueError("Performix attribution contradicts Linux perf beyond tolerance")
    return {
        "schema_version": "1.0.0",
        "passed": True,
        "disabled": asdict(disabled),
        "enabled": asdict(enabled),
        "linux_perf_kai_cycle_share": linux_perf_share,
        "absolute_share_difference": difference,
        "maximum_share_difference": maximum_share_difference,
    }


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _archive_members(archive: tarfile.TarFile) -> dict[str, tarfile.TarInfo]:
    members: dict[str, tarfile.TarInfo] = {}
    for member in archive.getmembers():
        if member.name in members:
            raise ValueError(f"Performix archive contains duplicate member: {member.name}")
        if member.name.startswith("/") or ".." in Path(member.name).parts:
            raise ValueError(f"Performix archive contains unsafe member: {member.name}")
        members[member.name] = member
    return members


def _member_bytes(
    archive: tarfile.TarFile,
    members: dict[str, tarfile.TarInfo],
    name: str,
) -> bytes:
    member = members.get(name)
    if member is None or not member.isfile():
        raise ValueError(f"Performix archive is missing file: {name}")
    stream = archive.extractfile(member)
    if stream is None:
        raise ValueError(f"Performix archive file cannot be read: {name}")
    return stream.read()


def _verify_internal_ledger(
    archive: tarfile.TarFile,
    members: dict[str, tarfile.TarInfo],
) -> int:
    ledger = _member_bytes(archive, members, "evidence/SHA256SUMS").decode("utf-8")
    checked = 0
    seen: set[str] = set()
    prefix = "/opt/armproof/evidence/"
    for line_number, line in enumerate(ledger.splitlines(), 1):
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64 or not parts[1].startswith(prefix):
            raise ValueError(f"invalid Performix checksum ledger line {line_number}")
        relative = parts[1][len(prefix):]
        name = f"evidence/{relative}"
        if name in seen:
            raise ValueError(f"duplicate Performix checksum ledger path: {relative}")
        seen.add(name)
        if _sha256_bytes(_member_bytes(archive, members, name)) != parts[0]:
            raise ValueError(f"Performix internal checksum mismatch: {relative}")
        checked += 1
    if checked < 1:
        raise ValueError("Performix checksum ledger is empty")
    return checked


def _parse_lscpu(text: str) -> dict[str, Any]:
    fields = {}
    for line in text.splitlines():
        if ":" in line:
            name, value = line.split(":", 1)
            fields[name.strip()] = value.strip()
    try:
        cpu_count = int(fields["CPU(s)"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Performix lscpu capture lacks a valid CPU count") from exc
    machine = {
        "architecture": fields.get("Architecture"),
        "cpu_count": cpu_count,
        "vendor_id": fields.get("Vendor ID"),
        "bios_vendor_id": fields.get("BIOS Vendor ID"),
        "model_name": fields.get("Model name"),
        "bios_model_name": fields.get("BIOS Model name"),
    }
    if machine["architecture"] not in {"aarch64", "arm64"}:
        raise ValueError("Performix machine capture is not Arm64")
    return machine


def verify_performix_archive(
    archive_path: Path,
    *,
    expected_archive_sha256: str,
    expected_experiment_id: str,
    disabled_run_id: str,
    enabled_run_id: str,
    linux_perf_share: float,
    maximum_share_difference: float,
) -> dict[str, Any]:
    """Verify one immutable archive and derive its matched Code Hotspots result."""
    if (
        len(expected_archive_sha256) != 64
        or any(char not in "0123456789abcdef" for char in expected_archive_sha256)
    ):
        raise ValueError("Performix archive SHA-256 is invalid")
    observed_archive_sha256 = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if observed_archive_sha256 != expected_archive_sha256:
        raise ValueError("Performix archive SHA-256 mismatch")
    if not expected_experiment_id or not disabled_run_id or not enabled_run_id:
        raise ValueError("Performix experiment and run IDs must be non-empty")
    if disabled_run_id == enabled_run_id:
        raise ValueError("Performix disabled and enabled run IDs must differ")
    identity_binding: dict[str, Any] | None = None
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = _archive_members(archive)
            checked = _verify_internal_ledger(archive, members)
            experiment = json.loads(
                _member_bytes(archive, members, "evidence/experiment.json")
            )
            if experiment.get("experiment_id") != expected_experiment_id:
                raise ValueError("Performix archive experiment ID mismatch")
            disabled = _member_bytes(
                archive,
                members,
                f"evidence/performix/exports/{disabled_run_id}.zip",
            )
            enabled = _member_bytes(
                archive,
                members,
                f"evidence/performix/exports/{enabled_run_id}.zip",
            )
            runtime_member = members.get("evidence/runtime-lock.json")
            if runtime_member is not None:
                runtime_bytes = _member_bytes(
                    archive, members, "evidence/runtime-lock.json"
                )
                runtime = json.loads(runtime_bytes)
                lscpu = _parse_lscpu(
                    _member_bytes(archive, members, "evidence/lscpu.txt").decode("utf-8")
                )
                uname = _member_bytes(
                    archive, members, "evidence/uname.txt"
                ).decode("utf-8").strip()
                if "aarch64" not in uname and "arm64" not in uname:
                    raise ValueError("Performix uname capture is not Arm64")
                treatments = experiment.get("treatments")
                if not isinstance(treatments, list) or len(treatments) != 2:
                    raise ValueError("Performix experiment lacks matched treatments")
                treatment_index = {
                    row.get("id"): row for row in treatments if isinstance(row, dict)
                }
                if set(treatment_index) != {"kleidiai-disabled", "kleidiai-enabled"}:
                    raise ValueError("Performix experiment treatment identities are invalid")
                disabled_row = treatment_index["kleidiai-disabled"]
                enabled_row = treatment_index["kleidiai-enabled"]
                for field in ("artifact_ref", "runtime_ref", "command_ref", "environment_overrides"):
                    if field not in disabled_row or field not in enabled_row:
                        raise ValueError(f"Performix experiment is missing {field}")
                normalized_artifacts = {
                    str(disabled_row["artifact_ref"]).replace(
                        "disabled overlay", "TREATMENT overlay"
                    ),
                    str(enabled_row["artifact_ref"]).replace(
                        "enabled overlay", "TREATMENT overlay"
                    ),
                }
                if len(normalized_artifacts) != 1 or (
                    disabled_row["runtime_ref"] != enabled_row["runtime_ref"]
                ):
                    raise ValueError("Performix model or runtime declarations do not match")
                model = runtime.get("model_int4")
                if not isinstance(model, dict):
                    raise ValueError("Performix runtime lock lacks the INT4 model identity")
                expected_model_ref = (
                    f"{model.get('id')}@{model.get('revision')}#{model.get('path')}"
                )
                if not next(iter(normalized_artifacts)).startswith(expected_model_ref):
                    raise ValueError("Performix model declaration contradicts its runtime lock")
                workload_ref = experiment.get("workload_ref")
                environment_ref = experiment.get("environment_ref")
                if not isinstance(workload_ref, str) or not workload_ref or not isinstance(
                    environment_ref, str
                ) or not environment_ref:
                    raise ValueError("Performix experiment workload or environment is missing")
                if any(
                    workload_ref not in str(row["command_ref"])
                    for row in (disabled_row, enabled_row)
                ):
                    raise ValueError("Performix commands do not use the declared workload")
                disabled_environment = disabled_row["environment_overrides"]
                enabled_environment = enabled_row["environment_overrides"]
                if not isinstance(disabled_environment, dict) or not isinstance(
                    enabled_environment, dict
                ):
                    raise ValueError("Performix treatment environments are invalid")
                disabled_control = disabled_environment.pop("mlas.disable_kleidiai", None)
                enabled_control = enabled_environment.pop("mlas.disable_kleidiai", None)
                if (
                    disabled_control != "1"
                    or enabled_control != "0"
                    or disabled_environment != enabled_environment
                ):
                    raise ValueError("Performix environments differ beyond the Arm control")
                identity_binding = {
                    "runtime_sha256": _sha256_bytes(runtime_bytes),
                    "model_ref": expected_model_ref,
                    "workload_ref": workload_ref,
                    "environment_ref": environment_ref,
                    "matched_environment": disabled_environment,
                    "machine": lscpu,
                    "uname": uname,
                }
    except (json.JSONDecodeError, tarfile.TarError, UnicodeDecodeError) as exc:
        raise ValueError("malformed Performix evidence archive") from exc
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        disabled_path = root / "disabled.zip"
        enabled_path = root / "enabled.zip"
        disabled_path.write_bytes(disabled)
        enabled_path.write_bytes(enabled)
        result = compare_code_hotspots(
            disabled_path,
            enabled_path,
            linux_perf_share=linux_perf_share,
            maximum_share_difference=maximum_share_difference,
        )
    if result["disabled"]["run_id"] != disabled_run_id:
        raise ValueError("Performix disabled export run ID mismatch")
    if result["enabled"]["run_id"] != enabled_run_id:
        raise ValueError("Performix enabled export run ID mismatch")
    return {
        **result,
        "experiment_id": expected_experiment_id,
        "archive_sha256": observed_archive_sha256,
        "internal_checksums": {"passed": True, "checked": checked},
        "identity_binding": identity_binding,
        "evidence_source": "native_arm_performix_code_hotspots_exports",
    }
