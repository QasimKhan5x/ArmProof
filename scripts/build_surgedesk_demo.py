#!/usr/bin/env python3
"""Generate the static SurgeDesk evidence payload."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from armproof.demo.surgedesk import build_surgedesk_payload  # noqa: E402


def main() -> int:
    output = ROOT / "surgedesk/data.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build_surgedesk_payload(ROOT), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
