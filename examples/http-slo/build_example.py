#!/usr/bin/env python3
"""Build a complete, checksum-bound http-slo-v1 adoption example."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[2]
VERSION = str(tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"])
ACTION_COMMIT = "32c1ad339b2a09d66af73aa391ed311962e215c7"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sample(request_id: str, latency_ms: float, scheduled_ns: int) -> str:
    finished = scheduled_ns + int(latency_ms * 1_000_000)
    return json.dumps({
        "request_id": request_id,
        "scheduled_ns": scheduled_ns,
        "started_ns": scheduled_ns,
        "finished_ns": finished,
        "latency_ms": latency_ms,
        "status_code": 200,
        "error": None,
        "response": {"request_id": request_id},
    }, sort_keys=True)


def _quality_sample(request_id: str, intent: str, latency_ms: float) -> str:
    return _sample(request_id, latency_ms, 0).replace(
        json.dumps({"request_id": request_id}, sort_keys=True),
        json.dumps({"output": json.dumps({"intent": intent})}, sort_keys=True),
    )


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
        interval_ns = int(10 * 1_000_000_000 / count)
        for repetition in range(1, 4):
            path = raw / f"{group}-{repetition}.jsonl"
            path.write_text(
                "\n".join(
                    _sample(
                        f"{group}-{repetition}-{index}",
                        latency_ms,
                        1_000_000_000 + index * interval_ns,
                    )
                    for index in range(count)
                )
                + "\n",
                encoding="utf-8",
            )
            boundaries[treatment][outcome].append(path.relative_to(evidence).as_posix())

    (evidence / "baseline.perf").write_text(
        "# Total Lost Samples: 0\n"
        "# Samples: 1,000 of event 'cycles:P'\n"
        "  92.00%  92.00% service libgeneric.so [.] generic_matmul\n",
        encoding="utf-8",
    )
    (evidence / "treatment.perf").write_text(
        "# Total Lost Samples: 0\n"
        "# Samples: 1,000 of event 'cycles:P'\n"
        "  70.00%  60.00% service libarm.so [.] kai_matmul_clamp\n",
        encoding="utf-8",
    )
    profiles = evidence / "profiles"
    profiles.mkdir()
    capacity_workload = identities_dir / "capacity.jsonl"
    capacity_workload.write_text(
        json.dumps({
            "request_id": "capacity-001",
            "payload": {"request_id": "capacity-001", "prompt": "representative request"},
        }, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    quality_workload = identities_dir / "quality.jsonl"
    quality_workload.write_text(
        "\n".join([
            json.dumps({
                "request_id": "quality-001",
                "payload": {"request_id": "quality-001"},
                "expected_intent": "card_help",
                "source_text": "card request",
            }, sort_keys=True),
            json.dumps({
                "request_id": "quality-002",
                "payload": {"request_id": "quality-002"},
                "expected_intent": "cash_help",
                "source_text": "cash request",
            }, sort_keys=True),
        ]) + "\n",
        encoding="utf-8",
    )
    quality_dir = evidence / "quality"
    quality_dir.mkdir()
    baseline_quality = "\n".join([
        _quality_sample("quality-001", "card_help", 10.0),
        _quality_sample("quality-002", "cash_help", 10.0),
    ]) + "\n"
    treatment_quality = "\n".join([
        _quality_sample("quality-001", "card_help", 8.0),
        _quality_sample("quality-002", "cash_help", 8.0),
    ]) + "\n"
    (quality_dir / "baseline-samples.jsonl").write_text(
        baseline_quality, encoding="utf-8"
    )
    (quality_dir / "treatment-samples.jsonl").write_text(
        treatment_quality, encoding="utf-8"
    )
    sources = {
        "artifact": identities_dir / "model.bin",
        "runtime": identities_dir / "runtime.lock",
        "workload": identities_dir / "workload-manifest.json",
        "environment": identities_dir / "environment.json",
    }
    contents = {
        "artifact": "same-model-artifact\n",
        "runtime": "same-runtime-revision\n",
        "workload": json.dumps({
            "schema_version": "1.0.0",
            "capacity_workload_sha256": _sha256(capacity_workload),
            "quality_workload_sha256": _sha256(quality_workload),
        }, sort_keys=True) + "\n",
        "environment": '{"machine":"example-arm-host"}\n',
    }
    for name, path in sources.items():
        path.write_text(contents[name], encoding="utf-8")

    common = {
        "artifact_sha256": _sha256(sources["artifact"]),
        "runtime_sha256": _sha256(sources["runtime"]),
        "workload_sha256": _sha256(sources["workload"]),
        "environment_sha256": _sha256(sources["environment"]),
    }
    commands = {
        "baseline": ("my-inference-server",),
        "treatment": ("my-inference-server",),
    }
    observed = {
        "baseline": {
            "treatment_id": "baseline",
            "sources": {
                "artifact": "identity-sources/model.bin",
                "runtime": "identity-sources/runtime.lock",
                "workload": "identity-sources/workload-manifest.json",
                "environment": "identity-sources/environment.json",
            },
            "controls": {"armproof.arm_acceleration_enabled": "false"},
        },
        "treatment": {
            "treatment_id": "optimized",
            "sources": {
                "artifact": "identity-sources/model.bin",
                "runtime": "identity-sources/runtime.lock",
                "workload": "identity-sources/workload-manifest.json",
                "environment": "identity-sources/environment.json",
            },
            "controls": {"armproof.arm_acceleration_enabled": "true"},
        },
    }
    _write_json(evidence / "identities.json", {
        "schema_version": "1.0.0",
        **observed,
    })
    profile_runs = {}
    for lane, report_name in (
        ("baseline", "baseline.perf"),
        ("treatment", "treatment.perf"),
    ):
        identity = observed[lane]
        command_payload = json.dumps(
            list(commands[lane]), separators=(",", ":")
        ).encode("utf-8")
        profile_runs[lane] = {
            "treatment_id": identity["treatment_id"],
            "report": report_name,
            "report_sha256": _sha256(evidence / report_name),
            "command_sha256": hashlib.sha256(command_payload).hexdigest(),
            **common,
            "controls": identity["controls"],
        }
    _write_json(profiles / "manifest.json", {
        "schema_version": "1.0.0",
        "profiler": "linux-perf",
        "event": "cycles:P",
        "runs": profile_runs,
    })
    _write_json(evidence / "protocol.json", {
        "schema_version": "1.0.0",
        "comparison_id": "http-slo-example",
        "measurement_seconds": 10.0,
        "p95_slo_ms": 10_000.0,
        "max_error_rate": 0.01,
        "minimum_delivery_ratio": 0.95,
        "minimum_requests_per_file": 2,
        "baseline_treatment_id": "baseline",
        "treatment_treatment_id": "optimized",
        "identity_manifest": "identities.json",
        "capacity_workload": "identity-sources/capacity.jsonl",
        "boundaries": boundaries,
        "arm_attribution": {
            "baseline_profile": "baseline.perf",
            "treatment_profile": "treatment.perf",
            "profile_manifest": "profiles/manifest.json",
            "symbol_regex": "kai_",
        },
        "quality": {
            "workload": "identity-sources/quality.jsonl",
            "baseline_samples": "quality/baseline-samples.jsonl",
            "treatment_samples": "quality/treatment-samples.jsonl",
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
            "command": list(commands[name]),
            **common,
            "environment": observed[name]["controls"],
        })
    _write_json(output / "contract.json", {
        "schema_version": "1.0.0",
        "contract_id": "http-slo-example",
        "treatments": treatments,
        "claims": [
            {
                "id": "capacity-lower-bound",
                "causal_scope": "arm_acceleration",
                "comparison_id": "http-slo-example",
                "metric": "capacity_ratio_lower_bound",
                "operator": "gte",
                "threshold": 2.0,
                "required_evidence": ["request_samples", "boundary_confirmations"],
                "required": True,
                "depends_on": ["quality-accuracy", "quality-macro-f1", "quality-schema"],
            },
            {
                "id": "arm-path",
                "causal_scope": "arm_acceleration",
                "comparison_id": "http-slo-example",
                "metric": "arm_path_treatment_observed",
                "operator": "eq",
                "threshold": 1.0,
                "required_evidence": ["arm_callchains"],
                "required": True,
                "depends_on": [],
            },
            {
                "id": "quality-accuracy",
                "causal_scope": "arm_acceleration",
                "comparison_id": "http-slo-example",
                "metric": "accuracy_delta_pp",
                "operator": "gte",
                "threshold": -1.0,
                "required_evidence": ["quality_rows", "workload_manifest"],
                "required": True,
                "depends_on": [],
            },
            {
                "id": "quality-macro-f1",
                "causal_scope": "arm_acceleration",
                "comparison_id": "http-slo-example",
                "metric": "macro_f1_delta_pp",
                "operator": "gte",
                "threshold": -1.0,
                "required_evidence": ["quality_rows", "workload_manifest"],
                "required": True,
                "depends_on": [],
            },
            {
                "id": "quality-schema",
                "causal_scope": "arm_acceleration",
                "comparison_id": "http-slo-example",
                "metric": "schema_valid_rate",
                "operator": "gte",
                "threshold": 0.99,
                "required_evidence": ["quality_rows", "workload_manifest"],
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
        "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7\n"
        f"      - uses: QasimKhan5x/ArmProof@{ACTION_COMMIT} # v{VERSION}\n"
        "        with:\n          config: armproof.json\n"
        f"          contract-sha256: {_sha256(output / 'contract.json')}\n",
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
