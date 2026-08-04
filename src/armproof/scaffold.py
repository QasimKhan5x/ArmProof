"""Generate a fail-closed starter kit for a bounded HTTP inference service."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_endpoint(endpoint: str) -> None:
    parsed = urlparse(endpoint)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or any(char.isspace() or char == "`" for char in endpoint)
    ):
        raise ValueError("endpoint must be a valid HTTP(S) URL")


def create_scaffold(output: Path, endpoint: str) -> tuple[Path, ...]:
    """Create templates without inventing evidence or overwriting owner files."""
    _validate_endpoint(endpoint)
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    workload = output / "workload.jsonl"
    workload.write_text(
        json.dumps(
            {
                "request_id": "replace-001",
                "payload": {
                    "request_id": "replace-001",
                    "prompt": "Replace this with a representative request",
                    "max_new_tokens": 32,
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    sources = output / "identity-sources"
    sources.mkdir(exist_ok=True)
    source_contents = {
        "artifact.ref": "replace with the deployed model artifact identity\n",
        "runtime.lock": "replace with pinned runtime and dependency revisions\n",
        "baseline-environment.json": '{"optimization":"disabled"}\n',
        "treatment-environment.json": '{"optimization":"enabled"}\n',
    }
    for name, content in source_contents.items():
        (sources / name).write_text(content, encoding="utf-8")

    common = {
        "artifact_sha256": _sha256(sources / "artifact.ref"),
        "runtime_sha256": _sha256(sources / "runtime.lock"),
        "workload_sha256": _sha256(workload),
    }
    treatments = []
    for treatment_id, environment_file, state in (
        ("baseline", "baseline-environment.json", "disabled"),
        ("optimized", "treatment-environment.json", "enabled"),
    ):
        treatments.append(
            {
                "id": treatment_id,
                "command": ["replace-with-service-command", "--endpoint", endpoint],
                **common,
                "environment_sha256": _sha256(sources / environment_file),
                "environment": {"optimization": state},
            }
        )
    _write_json(
        output / "contract.json",
        {
            "schema_version": "1.0.0",
            "contract_id": "replace-http-slo-contract",
            "treatments": treatments,
            "claims": [
                {
                    "id": "capacity-lower-bound",
                    "causal_scope": "cloud_capacity",
                    "comparison_id": "replace-http-slo-comparison",
                    "metric": "capacity_ratio_lower_bound",
                    "operator": "gte",
                    "threshold": 1.1,
                    "required_evidence": [
                        "request_samples",
                        "boundary_confirmations",
                    ],
                    "required": True,
                    "depends_on": [],
                },
                {
                    "id": "arm-path",
                    "causal_scope": "cloud_capacity",
                    "comparison_id": "replace-http-slo-comparison",
                    "metric": "arm_path_treatment_observed",
                    "operator": "eq",
                    "threshold": 1.0,
                    "required_evidence": ["arm_callchains"],
                    "required": True,
                    "depends_on": [],
                },
            ],
        },
    )
    _write_json(
        output / "armproof.json",
        {
            "schema_version": "1.0.0",
            "contract": "contract.json",
            "evidence": {
                "adapter": "http-slo-v1",
                "root": "evidence",
                "checksums": "evidence/SHA256SUMS",
                "protocol": "evidence/protocol.json",
            },
            "output": "report",
        },
    )
    _write_json(
        output / "collection-plan.json",
        {
            "schema_version": "1.0.0",
            "endpoint": endpoint,
            "adapter": "http-slo-v1",
            "workload": "workload.jsonl",
            "baseline_treatment_id": "baseline",
            "treatment_treatment_id": "optimized",
            "minimum_boundary_confirmations": 3,
            "required_outputs": [
                "raw passing and failing request rows for both treatments",
                "observed identity manifest",
                "baseline and treatment profiler outputs",
                "protocol.json and SHA256SUMS",
            ],
        },
    )

    workflow = output / ".github/workflows/armproof.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "name: ArmProof\non: [push, pull_request]\njobs:\n"
        "  verify:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - uses: QasimKhan5x/VerifyLane@v0.5.0\n"
        "        with:\n          config: armproof.json\n",
        encoding="utf-8",
    )
    (output / "ADOPTION_CHECKLIST.md").write_text(
        "# ArmProof Adoption Checklist\n\n"
        "- [ ] Replace the sample workload with representative requests.\n"
        "- [ ] Pin model, runtime, environment and service commands.\n"
        "- [ ] Set a service-level objective and claim threshold before testing.\n"
        "- [ ] Collect at least three passing and failing boundary confirmations.\n"
        "- [ ] Capture positive and negative Arm execution profiles separately.\n"
        "- [ ] Build `evidence/SHA256SUMS` after collection.\n"
        "- [ ] Run `armproof ci armproof.json`; missing evidence must block.\n",
        encoding="utf-8",
    )
    (output / "README.md").write_text(
        "# ArmProof HTTP Starter\n\n"
        f"Target endpoint: `{endpoint}`\n\n"
        "This scaffold intentionally contains no passing evidence. Start with "
        "`ADOPTION_CHECKLIST.md`, use the fixed-SLO collector, then place raw "
        "files under `evidence/`. Until that evidence is complete and "
        "checksum-bound, `armproof ci armproof.json` fails closed.\n\n"
        "See the complete executable shape in the upstream "
        "`examples/http-slo/` directory.\n",
        encoding="utf-8",
    )
    return tuple(
        output / relative
        for relative in (
            "armproof.json",
            "contract.json",
            "collection-plan.json",
            "workload.jsonl",
            "ADOPTION_CHECKLIST.md",
            "README.md",
            ".github/workflows/armproof.yml",
        )
    )
