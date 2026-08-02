#!/usr/bin/env python3
"""Demonstrate that ArmProof passes verified evidence and blocks tampering."""

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


def _config(root: Path, checksum_ledger: Path) -> Path:
    primary = ROOT / "ops/evidence/EXP-2026-004/accepted/evidence"
    reproduction = ROOT / "ops/evidence/EXP-2026-005/accepted/evidence"
    payload = {
        "schema_version": "1.0.0",
        "contract": str(ROOT / "examples/armproof-reference/contract.json"),
        "evidence": {
            "adapter": "kleidiai-capacity-v1",
            "root": str(primary),
            "checksums": str(checksum_ledger),
            "workload_manifest": str(ROOT / "data/banking77/generated/manifest.json"),
            "reproduction": {
                "root": str(reproduction),
                "checksums": str(reproduction / "SHA256SUMS"),
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
    primary = ROOT / "ops/evidence/EXP-2026-004/accepted/evidence"
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        valid_config = _config(temporary, primary / "SHA256SUMS")
        valid_status, valid_error = _run(valid_config, temporary / "valid-report")
        if valid_status != 0:
            print(f"UNEXPECTED FAILURE: {valid_error}", file=sys.stderr)
            return 1
        receipt = json.loads(
            (temporary / "valid-report/verification.json").read_text(encoding="utf-8")
        )
        checked = (
            receipt["checksums"]["checked"]
            + receipt["reproduction_checksums"]["checked"]
        )
        decision = json.loads(
            (temporary / "valid-report/decision.json").read_text(encoding="utf-8")
        )
        claim_count = len(decision["claims"])
        print(
            f"PASS    {claim_count}/{claim_count} claims from {checked} verified files"
        )

        lines = (primary / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        lines[0] = f"{'0' * 64}  {lines[0].split(maxsplit=1)[1]}"
        tampered_ledger = temporary / "TAMPERED-SHA256SUMS"
        tampered_ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
        tampered_config = _config(temporary, tampered_ledger)
        tampered_status, tampered_error = _run(
            tampered_config, temporary / "tampered-report"
        )
        if tampered_status != 1 or "checksum verification failed" not in tampered_error:
            print("UNEXPECTED RESULT: tampered evidence was not blocked", file=sys.stderr)
            return 1
        print("TAMPER  replaced one digest in a temporary copy of the primary ledger")
        print("BLOCK   release refused before policy evaluation: checksum mismatch")
    return 0


if __name__ == "__main__":
    raise SystemExit(demonstrate())
