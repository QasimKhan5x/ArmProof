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
    if len(sys.argv) not in {2, 3}:
        print("usage: write_github_summary.py DECISION.json [SUMMARY.json]", file=sys.stderr)
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
    if len(sys.argv) == 3:
        try:
            summary = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
            runtime = summary["runtime_memory"]
            experiment_ids = [
                runtime["sustained_experiment_id"],
                runtime["isolation_experiment_id"],
                runtime["simplification_experiment_id"],
            ]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            print(f"cannot render ArmProof runtime summary: {exc}", file=sys.stderr)
            return 1
        print()
        print("### Sustained Graviton runtime checks")
        print()
        print(f"- Status: **{'verified' if runtime['passed'] else 'blocked'}**")
        print(f"- Evidence: {_escape(' · '.join(experiment_ids))}")
        print(
            f"- Released floor: {_escape(runtime['candidate_rps'])} requests/s; "
            f"{_escape(runtime['confirmation_passes'])}/{_escape(runtime['confirmation_windows'])} "
            "long windows passed"
        )
        print(
            f"- Median p95 reduction: {_escape(round(runtime['p95_reduction_percent'], 2))}%"
        )
        if "raw_output_rows" in runtime:
            output_rows = f"{int(runtime['raw_output_rows']):,}"
            output_cases = f"{int(runtime['raw_output_cases']):,}"
            print(
                f"- Output equivalence: {_escape(output_rows)} raw responses "
                f"across {_escape(output_cases)} request cases"
            )
        if "complete_raw_rows" in runtime:
            complete_rows = f"{int(runtime['complete_raw_rows']):,}"
            print(
                f"- Full Stage 3 rederivation: {_escape(complete_rows)} "
                f"rows across {_escape(runtime['complete_raw_windows'])} windows"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
