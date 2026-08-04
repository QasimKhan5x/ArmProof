#!/usr/bin/env python3
"""Run the same sustained release decision used by SurgeDesk and CI."""

from __future__ import annotations

import io
import json
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from armproof.cli import main  # noqa: E402


def _run(config: Path, output: Path) -> tuple[int, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        status = main(["ci", str(config), "--output", str(output)])
    return status, stderr.getvalue().strip()


def _config(root: Path, archive: Path) -> Path:
    payload = {
        "schema_version": "1.0.0",
        "contract": str(ROOT / "examples/armproof-reference/sustained-contract.json"),
        "evidence": {
            "adapter": "kleidiai-sustained-v1",
            "archive": str(archive),
            "archive_sha256": (
                "f22e647aabe40eefd2abc5548306f40e2a5558ce1a85bc31c18319e6e51d78da"
            ),
            "workload_manifest": str(ROOT / "data/banking77/generated/manifest.json"),
            "performix": {
                "archive": str(
                    ROOT / "ops/evidence/EXP-2026-010/evidence.tar.gz"
                ),
                "archive_sha256": (
                    "28d411e40de38f3ad4a455bbfa09524dee8b44d6e44eb4d3b599e01635789148"
                ),
                "experiment_id": "EXP-2026-010",
                "disabled_run_id": "cbb01b949717",
                "enabled_run_id": "2bf254d4391b",
                "linux_perf_kai_cycle_share": 0.6853,
                "maximum_share_difference": 0.05,
            },
        },
        "deployment_summary": str(
            ROOT / "examples/armproof-reference/deployment-summary.json"
        ),
    }
    path = root / "armproof.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def demonstrate() -> int:
    archive = ROOT / "ops/evidence/EXP-2026-009/evidence.tar.gz"
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        valid_config = _config(temporary, archive)
        valid_status, valid_error = _run(valid_config, temporary / "valid-report")
        if valid_status != 0:
            print(f"UNEXPECTED FAILURE: {valid_error}", file=sys.stderr)
            return 1
        decision = json.loads(
            (temporary / "valid-report/decision.json").read_text(encoding="utf-8")
        )
        claim_count = len(decision["claims"])
        comparison = json.loads(
            (temporary / "valid-report/comparison.json").read_text(encoding="utf-8")
        )
        print(f"PASS    {claim_count}/{claim_count} claims from 4,200 raw request outcomes")
        print(
            "RELEASE at least "
            f"{comparison['metrics']['minimum_capacity_ratio']:.2f}x sustainable capacity"
        )

        tampered_archive = temporary / "altered-evidence.tar.gz"
        payload = bytearray(archive.read_bytes())
        payload[-1] ^= 1
        tampered_archive.write_bytes(payload)
        tampered_config = _config(temporary, tampered_archive)
        tampered_status, tampered_error = _run(
            tampered_config, temporary / "tampered-report"
        )
        if tampered_status != 1 or "digest" not in tampered_error:
            print("UNEXPECTED RESULT: tampered evidence was not blocked", file=sys.stderr)
            return 1
        print("BLOCK   altered archive refused before derivation")
    return 0


if __name__ == "__main__":
    raise SystemExit(demonstrate())
