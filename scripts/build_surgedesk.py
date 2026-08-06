#!/usr/bin/env python3
"""Generate the static SurgeDesk evidence payload."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from armproof.demo.surgedesk import build_surgedesk_payload  # noqa: E402


def render_payload() -> str:
    return json.dumps(build_surgedesk_payload(ROOT), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify",
        action="store_true",
        help="fail when surgedesk/data.json differs from accepted evidence",
    )
    args = parser.parse_args()
    output = ROOT / "surgedesk/data.json"
    rendered = render_payload()
    if args.verify:
        if not output.exists() or output.read_text(encoding="utf-8") != rendered:
            print(
                "SurgeDesk generated artifacts are stale; run scripts/build_surgedesk.py",
                file=sys.stderr,
            )
            return 1
        print(f"verified {output}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
