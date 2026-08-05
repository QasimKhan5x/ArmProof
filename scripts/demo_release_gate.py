#!/usr/bin/env python3
"""Run the canonical ArmProof release decision used by SurgeDesk and CI."""

from __future__ import annotations

import io
import json
import sys
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


def demonstrate(
    config: Path = ROOT / "examples/armproof-reference/armproof.json",
    output: Path = ROOT / "build/demo-release-gate",
) -> int:
    status, error = _run(config, output)
    if status != 0:
        print(f"FAIL    {error}", file=sys.stderr)
        return status

    decision = json.loads((output / "decision.json").read_text(encoding="utf-8"))
    comparison = json.loads((output / "comparison.json").read_text(encoding="utf-8"))
    claim_count = len(decision["claims"])
    metrics = comparison["metrics"]
    request_count = int(metrics.get("raw_confirmation_samples", 0))
    output_count = int(metrics.get("raw_quality_outputs", 0))
    profile_share = float(metrics.get("performix_enabled_kai_share", 0.0))

    print(f"PASS      {claim_count}/{claim_count} required release claims")
    print(
        "CAPACITY  at least "
        f"{metrics['minimum_capacity_ratio']:.2f}x at the fixed latency objective"
    )
    if request_count or output_count:
        print(
            f"EVIDENCE  {request_count:,} capacity requests and "
            f"{output_count:,} independently checked model outputs"
        )
    if profile_share:
        print(f"ARM PATH  {profile_share:.2%} of native Performix function samples")
    print("RELEASE   the measured Arm treatment is eligible for deployment")
    return 0


if __name__ == "__main__":
    raise SystemExit(demonstrate())
