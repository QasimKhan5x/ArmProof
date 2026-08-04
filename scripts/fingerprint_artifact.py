#!/usr/bin/env python3
"""Print one content-derived artifact identity for experiment capture."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

from armproof.artifacts import fingerprint_path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: fingerprint_artifact.py PATH")
    print(json.dumps({"source": asdict(fingerprint_path(Path(sys.argv[1])))}, sort_keys=True))


if __name__ == "__main__":
    main()
