#!/usr/bin/env python3
"""Build or verify the imported migration-measurement manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from armproof.evidence.manifest import build_manifest, verify_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    evidence_root = ROOT / "ops/evidence/imported-migration-measurements"
    manifest_path = evidence_root / "manifest.json"
    if args.verify:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        errors = verify_manifest(evidence_root, manifest)
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        print(f"Verified {len(manifest['files'])} evidence files.")
        return 0
    if args.source_root is None:
        parser.error("--source-root is required when building")
    archives = {
        "EXP-2026-001": args.source_root / "evidence/completed-exp001/evidence.tar.gz",
        "EXP-2026-002": args.source_root / "evidence/completed-exp002/evidence.tar.gz",
    }
    manifest = build_manifest(evidence_root, archives)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {manifest_path} with {len(manifest['files'])} evidence files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
