#!/usr/bin/env python3
"""Run the frozen one-sided capacity confirmation on a prepared Arm host."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path

from armproof.adapters.http_service import ExclusiveHttpServicePool, ManagedHttpService, ServiceSpec
from armproof.collectors.memory import parse_smaps_rollup
from armproof.evidence.identity import fingerprint_path
from armproof.experiments import (
    MinimumCapacityProtocol,
    TreatmentEndpoint,
    run_minimum_capacity_confirmation,
)
from armproof.quality import quality_from_dict
from armproof.reference.phi4 import create_ort_variant


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--precomputed-quality-dir", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    return parser.parse_args()


def load_protocol(path: Path) -> MinimumCapacityProtocol:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return MinimumCapacityProtocol(
        experiment_id=raw["experiment_id"],
        workload=Path.cwd() / raw["workload"],
        quality_dataset=Path.cwd() / raw["quality_dataset"],
        p95_slo_ms=raw["p95_slo_ms"],
        baseline_failing_rps=raw["baseline_failing_rps"],
        treatment_passing_rps=raw["treatment_passing_rps"],
        confirmation_seconds=raw["confirmation_seconds"],
        confirmations=raw["confirmations"],
        max_error_rate=raw["max_error_rate"],
        minimum_delivery_ratio=raw["minimum_delivery_ratio"],
        max_workers=raw["max_workers"],
        request_timeout_seconds=raw["request_timeout_seconds"],
        warmup_requests=raw["warmup_requests"],
        maximum_quality_loss_pp=raw["maximum_quality_loss_pp"],
        minimum_schema_valid_rate=raw["minimum_schema_valid_rate"],
        minimum_confirmation_requests=raw["minimum_confirmation_requests"],
        minimum_capacity_ratio=raw["minimum_capacity_ratio"],
    )


def main() -> int:
    args = parse_args()
    protocol = load_protocol(args.protocol)
    output = args.output.resolve()
    variants = output / "variants"
    enabled_model = create_ort_variant(args.model_source, variants / "enabled", True, 16)
    disabled_model = create_ort_variant(args.model_source, variants / "disabled", False, 16)
    identities = {
        "source": asdict(fingerprint_path(args.model_source)),
        "enabled": asdict(fingerprint_path(enabled_model)),
        "disabled": asdict(fingerprint_path(disabled_model)),
    }
    (output / "artifact-identities.json").write_text(
        json.dumps(identities, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    quality_results = {
        treatment_id: quality_from_dict(json.loads(
            (args.precomputed_quality_dir / f"{treatment_id}.json").read_text(
                encoding="utf-8"
            )
        ))
        for treatment_id in ("kleidiai-disabled", "kleidiai-enabled")
    }

    common_env = {
        "OMP_NUM_THREADS": "16",
        "OMP_PROC_BIND": "close",
        "OMP_PLACES": "cores",
        "PYTHONPATH": str(Path.cwd() / "src"),
    }
    specs = [
        ServiceSpec(
            treatment_id="kleidiai-disabled",
            command=(args.python, "-m", "armproof.reference.phi4", "--backend", "ort-int4",
                     "--model", str(disabled_model), "--label", "kleidiai-disabled",
                     "--port", "8000", "--threads", "16", "--max-inflight", "1"),
            environment=common_env,
            health_url="http://127.0.0.1:8000/health",
            request_url="http://127.0.0.1:8000/infer",
            log_path=output / "services/disabled.log",
            startup_timeout_seconds=180,
            request_timeout_seconds=protocol.request_timeout_seconds,
            cwd=Path.cwd(),
        ),
        ServiceSpec(
            treatment_id="kleidiai-enabled",
            command=(args.python, "-m", "armproof.reference.phi4", "--backend", "ort-int4",
                     "--model", str(enabled_model), "--label", "kleidiai-enabled",
                     "--port", "8001", "--threads", "16", "--max-inflight", "1"),
            environment=common_env,
            health_url="http://127.0.0.1:8001/health",
            request_url="http://127.0.0.1:8001/infer",
            log_path=output / "services/enabled.log",
            startup_timeout_seconds=180,
            request_timeout_seconds=protocol.request_timeout_seconds,
            cwd=Path.cwd(),
        ),
    ]
    with ExitStack() as stack:
        services = [stack.enter_context(ManagedHttpService(spec)) for spec in specs]
        pool = ExclusiveHttpServicePool(services)
        memory: dict[str, list[dict[str, object]]] = {
            treatment_id: [] for treatment_id in pool.index
        }

        def prepare_window(treatment_id: str, window_id: str) -> None:
            service = pool.activate(treatment_id)
            if service.pid is None:
                raise RuntimeError(f"service restart produced no PID for {window_id}")
            sample = parse_smaps_rollup(
                Path(f"/proc/{service.pid}/smaps_rollup").read_text(encoding="utf-8")
            )
            memory[treatment_id].append({
                **asdict(sample), "window_id": window_id, "pid": service.pid,
            })

        summary = run_minimum_capacity_confirmation(
            protocol,
            [
                TreatmentEndpoint("kleidiai-disabled", specs[0].request_url),
                TreatmentEndpoint("kleidiai-enabled", specs[1].request_url),
            ],
            output / "experiment",
            precomputed_quality=quality_results,
            prepare_window=prepare_window,
        )
    (output / "memory.json").write_text(
        json.dumps(memory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
