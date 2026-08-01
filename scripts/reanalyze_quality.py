#!/usr/bin/env python3
"""Re-score immutable request samples with the current versioned normalizer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from armproof.quality import evaluate_quality, load_quality_cases, quality_to_dict
from armproof.workload import RequestSample


def load_samples(path: Path) -> list[RequestSample]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        payload = json.loads(line)
        required = {
            "request_id", "scheduled_ns", "started_ns", "finished_ns", "latency_ms",
            "status_code", "error", "response",
        }
        if set(payload) != required:
            raise ValueError(f"unexpected sample fields on line {line_number}")
        rows.append(RequestSample(
            request_id=payload["request_id"], scheduled_ns=payload["scheduled_ns"],
            started_ns=payload["started_ns"], finished_ns=payload["finished_ns"],
            status_code=payload["status_code"], error=payload["error"],
            response=payload["response"],
        ))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_quality(load_quality_cases(args.dataset), load_samples(args.samples))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(quality_to_dict(result), indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "total": result.total,
        "accuracy": result.accuracy,
        "macro_f1": result.macro_f1,
        "schema_valid_rate": result.schema_valid_rate,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
