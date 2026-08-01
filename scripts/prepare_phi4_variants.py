#!/usr/bin/env python3
"""Create matched KleidiAI enabled/disabled overlays for the pinned INT4 model."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from armproof.reference import create_ort_variant  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=16)
    args = parser.parse_args()
    create_ort_variant(args.source, args.output_root / "kleidiai-disabled", False, args.threads)
    create_ort_variant(args.source, args.output_root / "kleidiai-enabled", True, args.threads)


if __name__ == "__main__":
    main()
