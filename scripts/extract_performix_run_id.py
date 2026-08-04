#!/usr/bin/env python3
"""Extract exactly one Performix run ID from APX JSON streamed on stdin."""

from __future__ import annotations

import sys

from armproof.evidence.performix import extract_run_id


def main() -> int:
    print(extract_run_id(sys.stdin.read()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
