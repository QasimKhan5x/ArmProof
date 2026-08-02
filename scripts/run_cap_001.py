#!/usr/bin/env python3
"""Run the preregistered CAP-001 workload on an already prepared Arm host."""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path

from armproof.adapters.http_service import ManagedHttpService, ServiceSpec
from armproof.collectors.memory import ProcessMemorySampler
from armproof.evidence.identity import fingerprint_path
from armproof.experiments import CapacityProtocol, MixProtocol, TreatmentEndpoint, run_capacity_experiment
from armproof.quality import (
    load_quality_cases,
    quality_from_dict,
    quality_to_dict,
    run_ort_batched_quality,
)
from armproof.reference.phi4 import create_ort_variant
from armproof.workload import write_samples_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--precomputed-quality-dir", type=Path)
    return parser.parse_args()


def load_protocol(path: Path) -> tuple[CapacityProtocol, int]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    root = Path.cwd()
    mixes = tuple(
        MixProtocol(
            row["mix_id"], root / row["workload"], row["p95_slo_ms"],
            tuple(row["candidates_rps"]),
        )
        for row in raw["mixes"]
    )
    return CapacityProtocol(
        experiment_id=raw["experiment_id"],
        mixes=mixes,
        quality_dataset=root / "data/banking77/generated/quality.jsonl",
        discovery_seconds=raw["discovery_seconds"],
        confirmation_seconds=raw["confirmation_seconds"],
        confirmations=raw["confirmations"],
        max_error_rate=raw["max_error_rate"],
        minimum_delivery_ratio=raw["minimum_delivery_ratio"],
        max_workers=raw["max_workers"],
        request_timeout_seconds=raw["request_timeout_seconds"],
        warmup_requests=raw["warmup_requests"],
        maximum_quality_loss_pp=raw.get("maximum_quality_loss_pp", 1.0),
        minimum_schema_valid_rate=raw.get("minimum_schema_valid_rate", 0.99),
        minimum_confirmation_requests=raw.get("minimum_confirmation_requests", 1),
        minimum_passing_mixes=raw.get("minimum_passing_mixes", 2),
        minimum_tested_ratio=raw.get("minimum_tested_ratio", 1.5),
        minimum_capacity_ratio_lower_bound=raw.get(
            "minimum_capacity_ratio_lower_bound", 1.15
        ),
    ), raw["quality_batch_size"]


def main() -> int:
    args = parse_args()
    protocol, quality_batch_size = load_protocol(args.protocol)
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

    quality_results = {}
    if args.precomputed_quality_dir:
        for treatment_id in ("kleidiai-disabled", "kleidiai-enabled"):
            quality_results[treatment_id] = quality_from_dict(json.loads(
                (args.precomputed_quality_dir / f"{treatment_id}.json").read_text(encoding="utf-8")
            ))
    else:
        cases = load_quality_cases(protocol.quality_dataset)
        for treatment_id, model_path in (
            ("kleidiai-disabled", disabled_model),
            ("kleidiai-enabled", enabled_model),
        ):
            result, samples = run_ort_batched_quality(
                model_path, cases, batch_size=quality_batch_size, label=treatment_id
            )
            quality_results[treatment_id] = result
            write_samples_jsonl(output / "quality-batch" / f"{treatment_id}-samples.jsonl", samples)
            (output / "quality-batch" / f"{treatment_id}.json").write_text(
                json.dumps(quality_to_dict(result), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

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
        samplers = [stack.enter_context(ProcessMemorySampler(service.pid or 0, 0.25)) for service in services]
        summary = run_capacity_experiment(
            protocol,
            [
                TreatmentEndpoint("kleidiai-disabled", specs[0].request_url),
                TreatmentEndpoint("kleidiai-enabled", specs[1].request_url),
            ],
            output / "experiment",
            precomputed_quality=quality_results,
        )
    memory = {
        spec.treatment_id: [asdict(sample) for sample in sampler.samples]
        for spec, sampler in zip(specs, samplers)
    }
    (output / "memory.json").write_text(
        json.dumps(memory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
