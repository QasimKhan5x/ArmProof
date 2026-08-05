"""Generate a fail-closed starter kit for a bounded HTTP inference service."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from armproof import __version__


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
    quality_workload = output / "quality.jsonl"
    quality_workload.write_text(
        json.dumps(
            {
                "request_id": "quality-001",
                "payload": {
                    "request_id": "quality-001",
                    "prompt": "Replace this with a labeled quality request",
                    "max_new_tokens": 32,
                },
                "expected_intent": "replace_intent",
                "source_text": "Replace this text",
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
        "environment.json": '{"machine":"replace-with-arm-machine"}\n',
    }
    for name, content in source_contents.items():
        (sources / name).write_text(content, encoding="utf-8")

    workload_manifest = sources / "workload-manifest.json"
    _write_json(workload_manifest, {
        "capacity_workload_sha256": _sha256(workload),
        "quality_workload_sha256": _sha256(quality_workload),
    })
    common = {
        "artifact_sha256": _sha256(sources / "artifact.ref"),
        "runtime_sha256": _sha256(sources / "runtime.lock"),
        "workload_sha256": _sha256(workload_manifest),
        "environment_sha256": _sha256(sources / "environment.json"),
    }
    treatments = []
    for treatment_id, enabled in (
        ("baseline", "false"),
        ("optimized", "true"),
    ):
        treatments.append(
            {
                "id": treatment_id,
                "command": ["replace-with-service-command", "--endpoint", endpoint],
                **common,
                "environment": {
                    "armproof.arm_acceleration_enabled": enabled,
                },
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
                    "causal_scope": "arm_acceleration",
                    "comparison_id": "replace-http-slo-comparison",
                    "metric": "capacity_ratio_lower_bound",
                    "operator": "gte",
                    "threshold": 1.1,
                    "required_evidence": [
                        "request_samples",
                        "boundary_confirmations",
                    ],
                    "required": True,
                    "depends_on": [
                        "quality-accuracy", "quality-macro-f1", "quality-schema"
                    ],
                },
                {
                    "id": "arm-path",
                    "causal_scope": "arm_acceleration",
                    "comparison_id": "replace-http-slo-comparison",
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
                    "comparison_id": "replace-http-slo-comparison",
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
                    "comparison_id": "replace-http-slo-comparison",
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
                    "comparison_id": "replace-http-slo-comparison",
                    "metric": "schema_valid_rate",
                    "operator": "gte",
                    "threshold": 0.99,
                    "required_evidence": ["quality_rows", "workload_manifest"],
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
    boundary_paths = {
        treatment: {
            outcome: [
                f"requests/{treatment}-{outcome}-{index}.jsonl"
                for index in range(1, 4)
            ]
            for outcome in ("pass", "fail")
        }
        for treatment in ("baseline", "treatment")
    }
    identity_source_paths = {
        "artifact": "evidence/identity-sources/artifact.ref",
        "runtime": "evidence/identity-sources/runtime.lock",
        "environment": "evidence/identity-sources/environment.json",
        "workload_manifest": "evidence/identity-sources/workload-manifest.json",
        "capacity_workload": "evidence/identity-sources/capacity.jsonl",
        "quality_workload": "evidence/identity-sources/quality.jsonl",
    }
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
            "minimum_requests_per_confirmation": 2,
            "request_schedule_tolerance_percent": 5,
            "expected_evidence_layout": {
                "protocol": "evidence/protocol.json",
                "identity_manifest": "evidence/identities.json",
                "profile_manifest": "evidence/profiles/manifest.json",
                "baseline_profile": "evidence/baseline.perf",
                "treatment_profile": "evidence/treatment.perf",
                "quality_baseline": "evidence/quality/baseline-samples.jsonl",
                "quality_treatment": "evidence/quality/treatment-samples.jsonl",
                "identity_sources": identity_source_paths,
                "boundaries": boundary_paths,
            },
            "required_outputs": [
                "distinct cadence-valid passing and failing request rows for both treatments",
                "observed identity manifest",
                "baseline and treatment parser-ready perf reports plus profile manifest",
                "baseline and treatment raw quality response samples",
                "protocol.json and SHA256SUMS",
            ],
        },
    )

    templates = output / "templates"
    template_sources = {
        "artifact": "identity-sources/artifact.ref",
        "runtime": "identity-sources/runtime.lock",
        "workload": "identity-sources/workload-manifest.json",
        "environment": "identity-sources/environment.json",
    }
    observed_identities = {
        lane: {
            "treatment_id": treatment_id,
            "sources": template_sources,
            "controls": {"armproof.arm_acceleration_enabled": enabled},
        }
        for lane, treatment_id, enabled in (
            ("baseline", "baseline", "false"),
            ("treatment", "optimized", "true"),
        )
    }
    _write_json(
        templates / "identities.json",
        {"schema_version": "1.0.0", **observed_identities},
    )
    _write_json(
        templates / "protocol.json",
        {
            "schema_version": "1.0.0",
            "comparison_id": "replace-http-slo-comparison",
            "measurement_seconds": 60.0,
            "p95_slo_ms": 10_000.0,
            "max_error_rate": 0.01,
            "minimum_delivery_ratio": 0.95,
            "minimum_requests_per_file": 2,
            "baseline_treatment_id": "baseline",
            "treatment_treatment_id": "optimized",
            "identity_manifest": "identities.json",
            "capacity_workload": "identity-sources/capacity.jsonl",
            "boundaries": boundary_paths,
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
        },
    )
    command_payload = json.dumps(
        ["replace-with-service-command", "--endpoint", endpoint],
        separators=(",", ":"),
    ).encode("utf-8")
    profile_common = {
        **common,
        "command_sha256": hashlib.sha256(command_payload).hexdigest(),
    }
    _write_json(
        templates / "profile-manifest.json",
        {
            "schema_version": "1.0.0",
            "profiler": "linux-perf",
            "event": "cycles:P",
            "runs": {
                lane: {
                    "treatment_id": identity["treatment_id"],
                    "report": f"{lane}.perf",
                    "report_sha256": "replace-after-profile-capture",
                    **profile_common,
                    "controls": identity["controls"],
                }
                for lane, identity in observed_identities.items()
            },
        },
    )

    workflow = output / ".github/workflows/armproof.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "name: ArmProof\non: [push, pull_request]\njobs:\n"
        "  verify:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7\n"
        "        with:\n          fetch-depth: 0\n"
        f"      - uses: QasimKhan5x/ArmProof@v{__version__}\n"
        "        with:\n          config: armproof.json\n"
        f"          contract-sha256: {_sha256(output / 'contract.json')}\n",
        encoding="utf-8",
    )
    (output / "ADOPTION_CHECKLIST.md").write_text(
        "# ArmProof Adoption Checklist\n\n"
        "- [ ] Replace the sample workload with representative requests.\n"
        "- [ ] Pin model, runtime, environment and service commands.\n"
        "- [ ] Set a service-level objective and claim threshold before testing.\n"
        "- [ ] Collect at least three passing and failing boundary confirmations.\n"
        "- [ ] Keep confirmation files distinct and preserve open-loop timestamps.\n"
        "- [ ] Capture positive and negative Arm execution profiles separately.\n"
        "- [ ] Bind parser-ready profiler reports to the treatment identities.\n"
        "- [ ] Collect raw HTTP quality responses from the same labeled dataset.\n"
        "- [ ] Copy the three JSON templates into the exact evidence paths and replace every placeholder.\n"
        "- [ ] Run `armproof seal armproof.json` after collection.\n"
        "- [ ] After editing `contract.json`, update `contract-sha256` in the workflow.\n"
        "- [ ] Run `armproof ci armproof.json`; missing evidence must block.\n",
        encoding="utf-8",
    )
    (output / "EVIDENCE_LAYOUT.md").write_text(
        "# Evidence Layout\n\n"
        "`collection-plan.json` contains these paths as machine-readable JSON. "
        "Collect each file from matched baseline and treatment runs; never reuse "
        "one confirmation under more than one name.\n\n"
        "```text\n"
        "evidence/\n"
        "  protocol.json\n"
        "  identities.json\n"
        "  baseline.perf\n"
        "  treatment.perf\n"
        "  profiles/manifest.json\n"
        "  quality/baseline-samples.jsonl\n"
        "  quality/treatment-samples.jsonl\n"
        "  requests/{baseline,treatment}-{pass,fail}-{1,2,3}.jsonl\n"
        "  identity-sources/artifact.ref\n"
        "  identity-sources/runtime.lock\n"
        "  identity-sources/environment.json\n"
        "  identity-sources/workload-manifest.json\n"
        "  identity-sources/capacity.jsonl\n"
        "  identity-sources/quality.jsonl\n"
        "```\n\n"
        "Start from `templates/protocol.json`, `templates/identities.json`, and "
        "`templates/profile-manifest.json`; copy them to the paths above and "
        "replace every placeholder with values from the measured runs. Copy the "
        "generated identity sources and workloads into the exact filenames shown.\n\n"
        "Use `armproof capacity` and `armproof quality` for request and quality "
        "rows. Add parser-ready profiler reports and their identity-bound manifest, "
        "then run:\n\n"
        "```bash\n"
        "armproof seal armproof.json\n"
        "armproof ci armproof.json\n"
        "```\n\n"
        "The templates use the exact parser shape. A complete measured example "
        "is executable under `examples/http-slo/` in the ArmProof repository.\n",
        encoding="utf-8",
    )
    (output / "README.md").write_text(
        "# ArmProof HTTP Starter\n\n"
        f"Target endpoint: `{endpoint}`\n\n"
        "This scaffold intentionally contains no passing evidence. Start with "
        "`ADOPTION_CHECKLIST.md`, use the fixed-SLO collector, then place raw "
        "files under `evidence/`. Until that evidence is complete and "
        "checksum-bound, `armproof ci armproof.json` fails closed.\n\n"
        "## Check The Empty Starter\n\n"
        "```bash\n"
        "python3.12 -m venv .venv\n"
        f".venv/bin/python -m pip install git+https://github.com/QasimKhan5x/ArmProof.git@v{__version__}\n"
        ".venv/bin/armproof ci armproof.json\n"
        "```\n\n"
        "The last command must fail because the starter has no measurements. "
        "Follow `EVIDENCE_LAYOUT.md` and `ADOPTION_CHECKLIST.md`. After collection:\n\n"
        "```bash\n"
        ".venv/bin/armproof seal armproof.json\n"
        ".venv/bin/armproof ci armproof.json\n"
        "```\n\n"
        "Replace both workload templates and the identity-source placeholders "
        "before collecting evidence. The `templates/` directory contains exact "
        "parser-ready JSON shapes; the collection plan names every required output.\n\n"
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
            "quality.jsonl",
            "identity-sources/artifact.ref",
            "identity-sources/runtime.lock",
            "identity-sources/environment.json",
            "identity-sources/workload-manifest.json",
            "templates/protocol.json",
            "templates/identities.json",
            "templates/profile-manifest.json",
            "ADOPTION_CHECKLIST.md",
            "EVIDENCE_LAYOUT.md",
            "README.md",
            ".github/workflows/armproof.yml",
        )
    )
