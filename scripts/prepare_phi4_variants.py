#!/usr/bin/env python3
"""Create matched KleidiAI enabled/disabled overlays for the pinned INT4 model."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from armproof.reference import create_ort_variant  # noqa: E402
from armproof.reference.phi4 import RELEASED_RUNTIME_TUNING  # noqa: E402

VARIANT_NAMES = ("kleidiai-disabled", "kleidiai-enabled")


def _clear_generated_variants(output_root: Path) -> None:
    """Remove only directories that carry ArmProof's generated-overlay identity."""
    entries = {path.name: path for path in output_root.iterdir()}
    unexpected = sorted(set(entries) - set(VARIANT_NAMES))
    if unexpected:
        raise ValueError(
            "refusing to replace a directory with non-ArmProof content: "
            + ", ".join(unexpected)
        )
    for path in entries.values():
        identity = path / "armproof_source_identity.json"
        if not path.is_dir() or not identity.is_file():
            raise ValueError(f"refusing to replace an unverified overlay: {path}")
    for path in entries.values():
        shutil.rmtree(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=16)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="replace an existing generated output directory",
    )
    args = parser.parse_args()
    if args.output_root.exists():
        if not args.replace:
            raise FileExistsError(
                f"variant output already exists; pass --replace: {args.output_root}"
            )
        _clear_generated_variants(args.output_root)
    create_ort_variant(args.source, args.output_root / "kleidiai-disabled", False, args.threads)
    create_ort_variant(
        args.source,
        args.output_root / "kleidiai-enabled",
        True,
        args.threads,
        session_overrides=RELEASED_RUNTIME_TUNING,
    )


if __name__ == "__main__":
    main()
