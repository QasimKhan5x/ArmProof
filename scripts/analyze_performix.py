#!/usr/bin/env python3
"""Normalize a matched native Performix Code Hotspots pair."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from armproof.evidence.performix import compare_code_hotspots


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--disabled", type=Path, required=True)
    parser.add_argument("--enabled", type=Path, required=True)
    parser.add_argument("--linux-perf-share", type=float, required=True)
    parser.add_argument("--maximum-share-difference", type=float, default=0.05)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare_code_hotspots(
        args.disabled, args.enabled,
        linux_perf_share=args.linux_perf_share,
        maximum_share_difference=args.maximum_share_difference,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
