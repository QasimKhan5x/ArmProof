#!/usr/bin/env python3
"""Generate the static SurgeDesk evidence payload."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from armproof.demo.surgedesk import build_surgedesk_payload  # noqa: E402
from serve_surgedesk import _adoption_receipt  # noqa: E402


def render_payload() -> str:
    return json.dumps(build_surgedesk_payload(ROOT), indent=2, sort_keys=True) + "\n"


def render_adoption() -> tuple[str, bytes]:
    receipt = _adoption_receipt()
    archive = base64.b64decode(receipt.pop("archive_base64"), validate=True)
    receipt["archive_href"] = "./armproof-service-starter.zip"
    return json.dumps(receipt, indent=2, sort_keys=True) + "\n", archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify",
        action="store_true",
        help="fail when surgedesk/data.json differs from accepted evidence",
    )
    args = parser.parse_args()
    output = ROOT / "surgedesk/data.json"
    adoption_output = ROOT / "surgedesk/adoption.json"
    starter_output = ROOT / "surgedesk/armproof-service-starter.zip"
    rendered = render_payload()
    adoption_rendered, starter_rendered = render_adoption()
    if args.verify:
        if (
            not output.exists()
            or output.read_text(encoding="utf-8") != rendered
            or not adoption_output.exists()
            or adoption_output.read_text(encoding="utf-8") != adoption_rendered
            or not starter_output.exists()
            or starter_output.read_bytes() != starter_rendered
        ):
            print(
                "SurgeDesk generated artifacts are stale; run scripts/build_surgedesk_demo.py",
                file=sys.stderr,
            )
            return 1
        print(f"verified {output}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    adoption_output.write_text(adoption_rendered, encoding="utf-8")
    starter_output.write_bytes(starter_rendered)
    print(f"{output}\n{adoption_output}\n{starter_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
