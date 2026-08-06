"""Generate a fail-closed starter kit for a bounded HTTP inference service."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from armproof import __version__
from armproof.scaffold_assets import (
    ADOPTION_CHECKLIST,
    EVIDENCE_LAYOUT,
    REFRESH_BINDINGS_SCRIPT,
    starter_readme,
)


ACTION_COMMIT = "32c1ad339b2a09d66af73aa391ed311962e215c7"


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


def _write_workloads(output: Path) -> tuple[Path, Path]:
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
    return workload, quality_workload


def _write_identity_sources(
    output: Path, workload: Path, quality_workload: Path
) -> dict[str, str]:
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
    return {
        "artifact_sha256": _sha256(sources / "artifact.ref"),
        "runtime_sha256": _sha256(sources / "runtime.lock"),
        "workload_sha256": _sha256(workload_manifest),
        "environment_sha256": _sha256(sources / "environment.json"),
    }


def _write_contract(output: Path, endpoint: str, common: dict[str, str]) -> None:
    treatments = [
        {
            "id": treatment_id,
            "command": ["replace-with-service-command", "--endpoint", endpoint],
            **common,
            "environment": {"armproof.arm_acceleration_enabled": enabled},
        }
        for treatment_id, enabled in (
            ("baseline", "false"),
            ("optimized", "true"),
        )
    ]
    claim_specs = (
        (
            "capacity-lower-bound",
            "capacity_ratio_lower_bound",
            "gte",
            1.1,
            ["request_samples", "boundary_confirmations"],
            ["quality-accuracy", "quality-macro-f1", "quality-schema"],
        ),
        ("arm-path", "arm_path_treatment_observed", "eq", 1.0, ["arm_callchains"], []),
        (
            "quality-accuracy",
            "accuracy_delta_pp",
            "gte",
            -1.0,
            ["quality_rows", "workload_manifest"],
            [],
        ),
        (
            "quality-macro-f1",
            "macro_f1_delta_pp",
            "gte",
            -1.0,
            ["quality_rows", "workload_manifest"],
            [],
        ),
        (
            "quality-schema",
            "schema_valid_rate",
            "gte",
            0.99,
            ["quality_rows", "workload_manifest"],
            [],
        ),
    )
    claims = [
        {
            "id": claim_id,
            "causal_scope": "arm_acceleration",
            "comparison_id": "replace-http-slo-comparison",
            "metric": metric,
            "operator": operator,
            "threshold": threshold,
            "required_evidence": evidence,
            "required": True,
            "depends_on": dependencies,
        }
        for claim_id, metric, operator, threshold, evidence, dependencies in claim_specs
    ]
    _write_json(
        output / "contract.json",
        {
            "schema_version": "1.0.0",
            "contract_id": "replace-http-slo-contract",
            "treatments": treatments,
            "claims": claims,
        },
    )


def _write_collection_templates(
    output: Path, endpoint: str, common: dict[str, str]
) -> None:
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


def create_scaffold(output: Path, endpoint: str) -> tuple[Path, ...]:
    """Create templates without inventing evidence or overwriting owner files."""
    _validate_endpoint(endpoint)
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    workload, quality_workload = _write_workloads(output)
    common = _write_identity_sources(output, workload, quality_workload)
    _write_contract(output, endpoint, common)
    _write_collection_templates(output, endpoint, common)

    workflow = output / ".github/workflows/armproof.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "name: ArmProof\non: [push, pull_request]\njobs:\n"
        "  verify:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7\n"
        "        with:\n          fetch-depth: 0\n"
        f"      - uses: QasimKhan5x/ArmProof@{ACTION_COMMIT} # v{__version__}\n"
        "        with:\n          config: armproof.json\n"
        f"          contract-sha256: {_sha256(output / 'contract.json')}\n",
        encoding="utf-8",
    )
    (output / "refresh_bindings.py").write_text(
        REFRESH_BINDINGS_SCRIPT, encoding="utf-8"
    )
    (output / "ADOPTION_CHECKLIST.md").write_text(
        ADOPTION_CHECKLIST, encoding="utf-8"
    )
    (output / "EVIDENCE_LAYOUT.md").write_text(EVIDENCE_LAYOUT, encoding="utf-8")
    (output / "README.md").write_text(
        starter_readme(endpoint, __version__), encoding="utf-8"
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
            "refresh_bindings.py",
            "ADOPTION_CHECKLIST.md",
            "EVIDENCE_LAYOUT.md",
            "README.md",
            ".github/workflows/armproof.yml",
        )
    )
