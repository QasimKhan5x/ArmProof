#!/usr/bin/env python3
"""Race one request across prepared KleidiAI control and treatment endpoints."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, NamedTuple, Sequence


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from armproof.demo.live import build_prompt  # noqa: E402
from armproof.workload import RequestInput  # noqa: E402
from armproof.workload.load import send_http_json  # noqa: E402


class LiveResult(NamedTuple):
    label: str
    backend: str
    latency_ms: float
    output: str


def _request(
    endpoint: str,
    label: str,
    expected_backend: str,
    prompt: str,
    timeout: float,
) -> LiveResult:
    request_id = f"demo-{expected_backend}-{uuid.uuid4().hex[:8]}"
    sample = send_http_json(
        endpoint,
        RequestInput(
            request_id,
            {
                "request_id": request_id,
                "prompt": prompt,
                "max_new_tokens": 32,
            },
        ),
        0,
        timeout,
    )
    if not sample.accepted or sample.response is None:
        raise ValueError(f"{label} request failed: {sample.error or sample.status_code}")
    response = sample.response
    backend = response.get("backend")
    output = response.get("output")
    if response.get("request_id") != request_id:
        raise ValueError(f"{label} returned the wrong request ID")
    if not isinstance(backend, str) or expected_backend not in backend.lower():
        raise ValueError(f"{label} returned unexpected backend {backend!r}")
    if not isinstance(output, str):
        raise ValueError(f"{label} returned no model output")
    return LiveResult(label, backend, sample.latency_ms, output)


def compare_live_requests(
    baseline_endpoint: str,
    optimized_endpoint: str,
    text: str,
    categories: Sequence[str],
    *,
    timeout: float = 60,
    on_complete: Callable[[LiveResult], None] | None = None,
) -> tuple[LiveResult, LiveResult]:
    """Issue the same prompt concurrently and retain control/treatment order."""
    prompt = build_prompt(text, categories)
    jobs = (
        (baseline_endpoint, "KleidiAI disabled", "kleidiai-disabled"),
        (optimized_endpoint, "KleidiAI enabled", "kleidiai-enabled"),
    )
    completed: dict[str, LiveResult] = {}
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(_request, endpoint, label, backend, prompt, timeout): label
            for endpoint, label, backend in jobs
        }
        for future in as_completed(futures):
            row = future.result()
            completed[row.label] = row
            if on_complete is not None:
                on_complete(row)
    return completed["KleidiAI disabled"], completed["KleidiAI enabled"]


def _categories() -> tuple[str, ...]:
    path = ROOT / "data/banking77/source/categories.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise ValueError("BANKING77 categories are invalid")
    return tuple(payload)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-endpoint", required=True)
    parser.add_argument("--optimized-endpoint", required=True)
    parser.add_argument(
        "--message",
        default="i have not received my card",
        help="customer request sent unchanged to both endpoints",
    )
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    print("LIVE ILLUSTRATION - NOT CAPACITY EVIDENCE", flush=True)
    print(f"Same request: {args.message}", flush=True)

    def show(row: LiveResult) -> None:
        print(
            f"  {row.label:<19} {row.latency_ms / 1000:>6.2f} s  "
            f"backend={row.backend}",
            flush=True,
        )

    try:
        baseline, optimized = compare_live_requests(
            args.baseline_endpoint,
            args.optimized_endpoint,
            args.message,
            _categories(),
            timeout=args.timeout,
            on_complete=show,
        )
    except (OSError, ValueError) as exc:
        print(f"live comparison failed: {exc}", file=sys.stderr)
        return 1

    ratio = baseline.latency_ms / optimized.latency_ms
    print(f"Illustrative request ratio: {ratio:.2f}x", flush=True)
    print("Capacity claim: use EXP-2026-009 sustained evidence (>=2.0x).", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
