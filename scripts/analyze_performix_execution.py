#!/usr/bin/env python3
"""Evaluate a frozen positive/negative Performix Code Hotspots gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from armproof.evidence.performix import compare_code_hotspots_execution


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--disabled", type=Path, required=True)
    parser.add_argument("--enabled", type=Path, required=True)
    parser.add_argument("--minimum-enabled-share", type=float, required=True)
    parser.add_argument("--minimum-total-samples", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare_code_hotspots_execution(
        args.disabled,
        args.enabled,
        minimum_enabled_share=args.minimum_enabled_share,
        minimum_total_samples=args.minimum_total_samples,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
