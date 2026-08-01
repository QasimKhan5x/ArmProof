#!/usr/bin/env python3
"""Render a compact, escaped GitHub job summary from an ArmProof decision."""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path


def _escape(value: object) -> str:
    return html.escape(str(value).replace("|", "\\|").replace("\n", " "))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: write_github_summary.py DECISION.json", file=sys.stderr)
        return 1
    try:
        decision = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        passed = decision["passed"]
        claims = decision["claims"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"cannot render ArmProof summary: {exc}", file=sys.stderr)
        return 1

    print(f"## ArmProof: {'verified' if passed else 'blocked'}")
    print()
    print("| Claim | Status | Observed | Threshold | Reason |")
    print("|---|---:|---:|---:|---|")
    for claim in claims:
        observed = "unknown" if claim.get("observed") is None else claim["observed"]
        print(
            f"| {_escape(claim.get('claim_id', 'unknown'))} "
            f"| {_escape(claim.get('status', 'unknown'))} "
            f"| {_escape(observed)} "
            f"| {_escape(claim.get('threshold', 'unknown'))} "
            f"| {_escape(claim.get('reason_code', 'unknown'))} |"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
