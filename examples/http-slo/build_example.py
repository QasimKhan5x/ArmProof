#!/usr/bin/env python3
"""Build a complete, checksum-bound http-slo-v1 adoption example."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sample(request_id: str, latency_ms: float) -> str:
    finished = int(latency_ms * 1_000_000)
    return json.dumps({
        "request_id": request_id,
        "scheduled_ns": 0,
        "started_ns": 0,
        "finished_ns": finished,
        "latency_ms": latency_ms,
        "status_code": 200,
        "error": None,
        "response": {"request_id": request_id},
    }, sort_keys=True)


def build(output: Path) -> Path:
    evidence = output / "evidence"
    raw = evidence / "requests"
    identities_dir = evidence / "identity-sources"
    raw.mkdir(parents=True, exist_ok=True)
    identities_dir.mkdir(parents=True, exist_ok=True)

    groups = {
        "baseline-pass": (2, 1_000.0),
        "baseline-fail": (3, 12_000.0),
        "treatment-pass": (6, 1_000.0),
        "treatment-fail": (7, 12_000.0),
    }
    boundaries = {
        name: {outcome: [] for outcome in ("pass", "fail")}
        for name in ("baseline", "treatment")
    }
    for group, (count, latency_ms) in groups.items():
        treatment, outcome = group.split("-")
        for repetition in range(1, 4):
            path = raw / f"{group}-{repetition}.jsonl"
            path.write_text(
                "\n".join(
                    _sample(f"{group}-{repetition}-{index}", latency_ms)
                    for index in range(count)
                )
                + "\n",
                encoding="utf-8",
            )
            boundaries[treatment][outcome].append(path.relative_to(evidence).as_posix())

    (evidence / "baseline.perf").write_text(
        "generic_matmul reference path\n", encoding="utf-8"
    )
    (evidence / "treatment.perf").write_text(
        "kai_matmul_clamp optimized Arm path\n", encoding="utf-8"
    )
    sources = {
        "artifact": identities_dir / "model.bin",
        "runtime": identities_dir / "runtime.lock",
        "workload": identities_dir / "workload.jsonl",
        "baseline_environment": identities_dir / "baseline-environment.json",
        "treatment_environment": identities_dir / "treatment-environment.json",
    }
    contents = {
        "artifact": "same-model-artifact\n",
        "runtime": "same-runtime-revision\n",
        "workload": "same-request-workload\n",
        "baseline_environment": '{"optimization":"disabled"}\n',
        "treatment_environment": '{"optimization":"enabled"}\n',
    }
    for name, path in sources.items():
        path.write_text(contents[name], encoding="utf-8")

    common = {
        "artifact_sha256": _sha256(sources["artifact"]),
        "runtime_sha256": _sha256(sources["runtime"]),
        "workload_sha256": _sha256(sources["workload"]),
    }
    observed = {
        "baseline": {
            "treatment_id": "baseline",
            **common,
            "environment_sha256": _sha256(sources["baseline_environment"]),
            "controls": {"optimization": "disabled"},
        },
        "treatment": {
            "treatment_id": "optimized",
            **common,
            "environment_sha256": _sha256(sources["treatment_environment"]),
            "controls": {"optimization": "enabled"},
        },
    }
    _write_json(evidence / "identities.json", {
        "schema_version": "1.0.0",
        **observed,
    })
    _write_json(evidence / "protocol.json", {
        "schema_version": "1.0.0",
        "comparison_id": "http-slo-example",
        "measurement_seconds": 10.0,
        "p95_slo_ms": 10_000.0,
        "max_error_rate": 0.01,
        "minimum_delivery_ratio": 0.95,
        "minimum_requests_per_file": 1,
        "baseline_treatment_id": "baseline",
        "treatment_treatment_id": "optimized",
        "identity_manifest": "identities.json",
        "boundaries": boundaries,
        "arm_attribution": {
            "baseline_profile": "baseline.perf",
            "treatment_profile": "treatment.perf",
            "symbol_regex": "kai_",
        },
    })
    ledger_rows = []
    for path in sorted(item for item in evidence.rglob("*") if item.is_file()):
        relative = path.relative_to(evidence).as_posix()
        ledger_rows.append(
            f"{_sha256(path)}  /opt/armproof/evidence/{relative}\n"
        )
    (evidence / "SHA256SUMS").write_text("".join(ledger_rows), encoding="utf-8")

    treatments = []
    for name in ("baseline", "treatment"):
        row = observed[name]
        treatments.append({
            "id": row["treatment_id"],
            "command": ["my-inference-server"],
            "artifact_sha256": row["artifact_sha256"],
            "runtime_sha256": row["runtime_sha256"],
            "workload_sha256": row["workload_sha256"],
            "environment_sha256": row["environment_sha256"],
            "environment": row["controls"],
        })
    _write_json(output / "contract.json", {
        "schema_version": "1.0.0",
        "contract_id": "http-slo-example",
        "treatments": treatments,
        "claims": [
            {
                "id": "capacity-lower-bound",
                "causal_scope": "cloud_capacity",
                "comparison_id": "http-slo-example",
                "metric": "capacity_ratio_lower_bound",
                "operator": "gte",
                "threshold": 2.0,
                "required_evidence": ["request_samples", "boundary_confirmations"],
                "required": True,
                "depends_on": [],
            },
            {
                "id": "arm-path",
                "causal_scope": "cloud_capacity",
                "comparison_id": "http-slo-example",
                "metric": "arm_path_treatment_observed",
                "operator": "eq",
                "threshold": 1.0,
                "required_evidence": ["arm_callchains"],
                "required": True,
                "depends_on": [],
            },
        ],
    })
    _write_json(output / "armproof.json", {
        "schema_version": "1.0.0",
        "contract": "contract.json",
        "evidence": {
            "adapter": "http-slo-v1",
            "root": "evidence",
            "checksums": "evidence/SHA256SUMS",
            "protocol": "evidence/protocol.json",
        },
        "output": "report",
    })
    workflow = output / ".github/workflows/armproof.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "name: ArmProof\non: [push, pull_request]\njobs:\n"
        "  verify:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - uses: QasimKhan5x/ArmProof@v0.5.1\n"
        "        with:\n          config: armproof.json\n",
        encoding="utf-8",
    )
    return output / "armproof.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build(args.output.resolve()))


if __name__ == "__main__":
    main()
