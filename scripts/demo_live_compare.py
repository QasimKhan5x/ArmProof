#!/usr/bin/env python3
"""Preflight one request through each configured Graviton endpoint."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import uuid
from pathlib import Path
from typing import Callable, NamedTuple, Sequence
from urllib.parse import urlsplit


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


def _health_url(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    return parsed._replace(path="/health", query="", fragment="").geturl()


def verify_live_identities(
    baseline_endpoint: str, optimized_endpoint: str, timeout: float
) -> dict[str, object]:
    payloads = []
    for endpoint in (baseline_endpoint, optimized_endpoint):
        with urllib.request.urlopen(_health_url(endpoint), timeout=timeout) as response:
            payload = json.load(response)
        if not isinstance(payload, dict) or payload.get("ready") is not True:
            raise ValueError("endpoint health document is not ready")
        payloads.append(payload)
    baseline, optimized = payloads
    matched = (
        "model_identity", "source_artifact_sha256", "runtime", "runtime_version",
        "threads", "architecture", "cpu_affinity",
    )
    if any(baseline.get(field) != optimized.get(field) for field in matched):
        raise ValueError("endpoint model, runtime, thread, or CPU identity differs")
    if (
        baseline.get("backend") != "kleidiai-disabled"
        or optimized.get("backend") != "kleidiai-enabled"
        or baseline.get("optimization_control", {}).get("mlas.disable_kleidiai") != "1"
        or optimized.get("optimization_control", {}).get("mlas.disable_kleidiai") != "0"
    ):
        raise ValueError("endpoint KleidiAI controls do not form the matched pair")
    return {
        field: baseline[field]
        for field in (
            "source_artifact_sha256", "runtime", "runtime_version", "threads",
            "architecture", "cpu_affinity",
        )
    }


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
    """Issue the same prompt sequentially and retain control/treatment order."""
    prompt = build_prompt(text, categories)
    jobs = (
        (baseline_endpoint, "KleidiAI disabled", "kleidiai-disabled"),
        (optimized_endpoint, "KleidiAI enabled", "kleidiai-enabled"),
    )
    completed: dict[str, LiveResult] = {}
    for endpoint, label, backend in jobs:
        row = _request(endpoint, label, backend, prompt, timeout)
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

    print("LIVE GRAVITON ENDPOINT PREFLIGHT", flush=True)
    print(f"Customer request: {args.message}", flush=True)

    def show(row: LiveResult) -> None:
        print(
            f"  {row.label:<19} {row.latency_ms / 1000:>6.2f} s  "
            f"backend={row.backend}",
            flush=True,
        )

    try:
        identity = verify_live_identities(
            args.baseline_endpoint, args.optimized_endpoint, args.timeout
        )
        print(
            f"Matched runtime: {identity['runtime']} {identity['runtime_version']} · "
            f"{identity['architecture']} · {identity['threads']} threads · "
            f"source={str(identity['source_artifact_sha256'])[:12]}…",
            flush=True,
        )
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

    print(
        "READY matched endpoint identities verified; request latency is a warm-up observation.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
