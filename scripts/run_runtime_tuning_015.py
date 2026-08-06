#!/usr/bin/env python3
"""Screen and confirm bounded ONNX Runtime tuning candidates on Graviton."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from armproof.adapters.http_service import ExclusiveHttpServicePool, ManagedHttpService, ServiceSpec
from armproof.collectors.memory import parse_smaps_rollup
from armproof.reference.phi4 import create_ort_variant
from armproof.workload import load_requests_jsonl, materialize_requests, run_open_loop, summarize_samples, write_samples_jsonl
from armproof.workload.io import summary_to_dict
from armproof.workload.load import send_http_json


THREAD_OPTIONS = {
    "session.intra_op.spin_duration_us": "1000",
    "session.intra_op.spin_backoff_max": "8",
    "session.dynamic_block_base": "4",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--mimalloc-library", type=Path)
    parser.add_argument("--python", default=sys.executable)
    return parser.parse_args()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _current_thp(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    selected = [item[1:-1] for item in text.split() if item.startswith("[") and item.endswith("]")]
    if len(selected) != 1:
        raise ValueError(f"cannot identify current THP mode from: {text}")
    return selected[0]


def _response_digest(samples: list[Any]) -> str:
    outputs = []
    for sample in sorted(samples, key=lambda item: item.request_id):
        if not sample.accepted or sample.response is None:
            raise RuntimeError("output-equivalence sample was not accepted")
        outputs.append(sample.response.get("output"))
    return hashlib.sha256(
        json.dumps(outputs, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _passes(summary: dict[str, Any], rate: float, protocol: dict[str, Any]) -> bool:
    return bool(
        summary["p95_ms"] is not None
        and summary["p95_ms"] <= protocol["p95_slo_ms"]
        and summary["error_rate"] <= protocol["max_error_rate"]
        and summary["accepted_rps"] >= rate * protocol["minimum_delivery_ratio"]
    )


def main() -> int:
    args = parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    workload = load_requests_jsonl(Path.cwd() / protocol["workload"])
    thp_path = Path("/sys/kernel/mm/transparent_hugepage/enabled")
    original_thp = _current_thp(thp_path)

    mimalloc_available = bool(args.mimalloc_library and args.mimalloc_library.is_file())
    variant_set = protocol.get("variant_set", "primary")
    if variant_set == "simplified-confirmation":
        if not mimalloc_available:
            raise RuntimeError("simplified confirmation requires mimalloc")
        variants = [
            {"id": "mimalloc-thp", "session": {}, "mimalloc": True, "thp": "always"},
        ]
    elif variant_set == "thp-isolation":
        variants: list[dict[str, Any]] = [
            {"id": "current", "session": {}, "mimalloc": False, "thp": original_thp},
            {"id": "thp-only", "session": {}, "mimalloc": False, "thp": "always"},
            {"id": "thread-thp", "session": THREAD_OPTIONS, "mimalloc": False, "thp": "always"},
        ]
        if mimalloc_available:
            variants.append(
                {"id": "mimalloc-thp", "session": {}, "mimalloc": True, "thp": "always"}
            )
    else:
        variants = [
            {"id": "current", "session": {}, "mimalloc": False, "thp": original_thp},
            {"id": "thread-tuned", "session": THREAD_OPTIONS, "mimalloc": False, "thp": original_thp},
        ]
        if mimalloc_available:
            variants.extend([
                {"id": "mimalloc", "session": {}, "mimalloc": True, "thp": original_thp},
                {"id": "thread-memory", "session": THREAD_OPTIONS, "mimalloc": True, "thp": "always"},
            ])

    services = []
    variant_models: dict[str, Path] = {}
    for index, variant in enumerate(variants):
        variant_id = variant["id"]
        model = create_ort_variant(
            args.model_source,
            output / "variants" / variant_id,
            True,
            protocol["threads"],
            session_overrides=variant["session"],
        )
        variant_models[variant_id] = model
        environment = {
            "OMP_NUM_THREADS": str(protocol["threads"]),
            "OMP_PROC_BIND": "close",
            "OMP_PLACES": "cores",
            "PYTHONPATH": str(Path.cwd() / "src"),
        }
        if variant["mimalloc"]:
            environment["LD_PRELOAD"] = str(args.mimalloc_library.resolve())
        port = 8100 + index
        services.append(ManagedHttpService(ServiceSpec(
            treatment_id=variant_id,
            command=(
                args.python, "-m", "armproof.reference.phi4", "--backend", "ort-int4",
                "--model", str(model), "--label", variant_id, "--port", str(port),
                "--threads", str(protocol["threads"]), "--max-inflight", "1",
            ),
            environment=environment,
            health_url=f"http://127.0.0.1:{port}/health",
            request_url=f"http://127.0.0.1:{port}/infer",
            log_path=output / "services" / f"{variant_id}.log",
            startup_timeout_seconds=180,
            request_timeout_seconds=protocol["request_timeout_seconds"],
            cwd=Path.cwd(),
        )))

    pool = ExclusiveHttpServicePool(services)
    rows: list[dict[str, Any]] = []
    output_digests: dict[str, str] = {}

    def run_window(variant_id: str, phase: str, repetition: int, seconds: float) -> dict[str, Any]:
        variant = next(item for item in variants if item["id"] == variant_id)
        thp_path.write_text(variant["thp"], encoding="utf-8")
        service = pool.activate(variant_id)
        if service.pid is None:
            raise RuntimeError("service has no PID")
        warm = materialize_requests(workload, protocol["warmup_requests"], f"warm-{phase}-{repetition}")
        warm_samples = run_open_loop(
            warm,
            lambda item, scheduled: send_http_json(
                service.spec.request_url, item, scheduled, protocol["request_timeout_seconds"]
            ),
            target_rps=protocol["warmup_rps"],
            max_workers=protocol["max_workers"],
        )
        if not all(item.accepted for item in warm_samples):
            raise RuntimeError(f"warmup failed for {variant_id}")
        digest = _response_digest(warm_samples)
        output_digests.setdefault(variant_id, digest)
        count = round(protocol["candidate_rps"] * seconds)
        requests = materialize_requests(workload, count, f"{phase}-{repetition}-{variant_id}")
        samples = run_open_loop(
            requests,
            lambda item, scheduled: send_http_json(
                service.spec.request_url, item, scheduled, protocol["request_timeout_seconds"]
            ),
            target_rps=protocol["candidate_rps"],
            max_workers=protocol["max_workers"],
        )
        sample_path = output / phase / variant_id / f"rep-{repetition}.jsonl"
        write_samples_jsonl(sample_path, samples)
        summary = summary_to_dict(summarize_samples(samples, seconds))
        memory = asdict(parse_smaps_rollup(
            Path(f"/proc/{service.pid}/smaps_rollup").read_text(encoding="utf-8")
        ))
        row = {
            "phase": phase,
            "variant_id": variant_id,
            "repetition": repetition,
            "seconds": seconds,
            "target_rps": protocol["candidate_rps"],
            "passed": _passes(summary, protocol["candidate_rps"], protocol),
            "summary": summary,
            "memory": memory,
            "thp_mode": _current_thp(thp_path),
            "output_digest": digest,
        }
        rows.append(row)
        _write_json(sample_path.with_suffix(".summary.json"), row)
        return row

    try:
        if variant_set == "simplified-confirmation":
            for repetition in range(1, protocol["confirmation_repetitions"] + 1):
                run_window(
                    "mimalloc-thp", "confirmation", repetition,
                    protocol["confirmation_seconds"],
                )
        else:
            for repetition in range(1, protocol["screen_repetitions"] + 1):
                order = variants if repetition % 2 else list(reversed(variants))
                for variant in order:
                    run_window(variant["id"], "screen", repetition, protocol["screen_seconds"])

            current_rows = [row for row in rows if row["phase"] == "screen" and row["variant_id"] == "current"]
            current_p95 = statistics.median(row["summary"]["p95_ms"] for row in current_rows)
            outputs_equivalent = len({row["output_digest"] for row in rows}) == 1
            candidates = []
            for variant in variants:
                if variant["id"] == "current":
                    continue
                candidate_rows = [
                    row for row in rows
                    if row["phase"] == "screen" and row["variant_id"] == variant["id"]
                ]
                candidate_p95 = statistics.median(row["summary"]["p95_ms"] for row in candidate_rows)
                improvement = (current_p95 - candidate_p95) / current_p95
                if (
                    outputs_equivalent
                    and all(row["passed"] for row in candidate_rows)
                    and improvement >= protocol["minimum_screen_improvement"]
                ):
                    candidates.append((candidate_p95, variant["id"], improvement))

            winner = min(candidates)[1] if candidates else None
            if winner and not protocol.get("screen_only", False):
                for repetition in range(1, protocol["confirmation_repetitions"] + 1):
                    order = ("current", winner) if repetition % 2 else (winner, "current")
                    for variant_id in order:
                        run_window(
                            variant_id, "confirmation", repetition,
                            protocol["confirmation_seconds"],
                        )
    finally:
        for service in services:
            service.stop()
        thp_path.write_text(original_thp, encoding="utf-8")

    confirmation = [row for row in rows if row["phase"] == "confirmation"]
    outputs_equivalent = len({row["output_digest"] for row in rows}) == 1
    accepted = False
    if variant_set == "simplified-confirmation":
        winner = "mimalloc-thp"
        winner_rows = [row for row in confirmation if row["variant_id"] == winner]
        expected_digest = protocol["expected_output_digest"]
        outputs_equivalent = bool(
            output_digests.get(winner) == expected_digest
            and all(row["output_digest"] == expected_digest for row in rows)
        )
        accepted = bool(
            len(winner_rows) == protocol["confirmation_repetitions"]
            and all(row["passed"] for row in winner_rows)
            and outputs_equivalent
        )
    elif winner and not protocol.get("screen_only", False):
        winner_rows = [row for row in confirmation if row["variant_id"] == winner]
        control_rows = [row for row in confirmation if row["variant_id"] == "current"]
        accepted = bool(
            len(winner_rows) == protocol["confirmation_repetitions"]
            and all(row["passed"] for row in winner_rows)
            and all(not row["passed"] for row in control_rows)
            and outputs_equivalent
        )
    result = {
        "schema_version": "1.0.0",
        "experiment_id": protocol["experiment_id"],
        "mimalloc_available": mimalloc_available,
        "original_thp_mode": original_thp,
        "variants": variants,
        "output_digests": output_digests,
        "outputs_equivalent": outputs_equivalent,
        "winner": winner,
        "screen_only": bool(protocol.get("screen_only", False)),
        "accepted": accepted,
        "rows": rows,
    }
    _write_json(output / "summary.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
