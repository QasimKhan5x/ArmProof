"""Generate a fail-closed starter kit for a bounded HTTP inference service."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from armproof import __version__


ACTION_COMMIT = "6a2785eccca0e42d36fcf37919bfc83dfca3ea6a"


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
        f"      - uses: QasimKhan5x/ArmProof@{ACTION_COMMIT} # v{__version__}\n"
        "        with:\n          config: armproof.json\n"
        f"          contract-sha256: {_sha256(output / 'contract.json')}\n",
        encoding="utf-8",
    )
    (output / "refresh_bindings.py").write_text(
        '''#!/usr/bin/env python3
"""Refresh starter identities after replacing placeholders and before collection."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\\n", encoding="utf-8")


workload_manifest = ROOT / "identity-sources/workload-manifest.json"
write(workload_manifest, {
    "capacity_workload_sha256": sha256(ROOT / "workload.jsonl"),
    "quality_workload_sha256": sha256(ROOT / "quality.jsonl"),
})
common = {
    "artifact_sha256": sha256(ROOT / "identity-sources/artifact.ref"),
    "runtime_sha256": sha256(ROOT / "identity-sources/runtime.lock"),
    "workload_sha256": sha256(workload_manifest),
    "environment_sha256": sha256(ROOT / "identity-sources/environment.json"),
}
contract_path = ROOT / "contract.json"
contract = load(contract_path)
for treatment in contract["treatments"]:
    treatment.update(common)
write(contract_path, contract)

evidence_root = ROOT / "evidence"
(evidence_root / "identity-sources").mkdir(parents=True, exist_ok=True)
(evidence_root / "profiles").mkdir(parents=True, exist_ok=True)
(evidence_root / "quality").mkdir(parents=True, exist_ok=True)
(evidence_root / "requests").mkdir(parents=True, exist_ok=True)
for source, destination in (
    ("templates/protocol.json", "evidence/protocol.json"),
    ("templates/identities.json", "evidence/identities.json"),
    ("identity-sources/artifact.ref", "evidence/identity-sources/artifact.ref"),
    ("identity-sources/runtime.lock", "evidence/identity-sources/runtime.lock"),
    ("identity-sources/environment.json", "evidence/identity-sources/environment.json"),
    ("identity-sources/workload-manifest.json", "evidence/identity-sources/workload-manifest.json"),
    ("workload.jsonl", "evidence/identity-sources/capacity.jsonl"),
    ("quality.jsonl", "evidence/identity-sources/quality.jsonl"),
):
    shutil.copyfile(ROOT / source, ROOT / destination)

profile_path = ROOT / "templates/profile-manifest.json"
profile = load(profile_path)
treatments = {row["id"]: row for row in contract["treatments"]}
for run in profile["runs"].values():
    treatment = treatments[run["treatment_id"]]
    run.update(common)
    command = json.dumps(treatment["command"], separators=(",", ":")).encode("utf-8")
    run["command_sha256"] = hashlib.sha256(command).hexdigest()
    report = evidence_root / run["report"]
    if report.is_file():
        run["report_sha256"] = sha256(report)
write(profile_path, profile)
write(evidence_root / "profiles/manifest.json", profile)

workflow_path = ROOT / ".github/workflows/armproof.yml"
workflow = workflow_path.read_text(encoding="utf-8")
workflow = re.sub(
    r"contract-sha256: [0-9a-f]{64}",
    f"contract-sha256: {sha256(contract_path)}",
    workflow,
)
workflow_path.write_text(workflow, encoding="utf-8")
print("Refreshed evidence layout, identities, commands, contract, and workflow digests.")
''',
        encoding="utf-8",
    )
    (output / "ADOPTION_CHECKLIST.md").write_text(
        "# ArmProof Adoption Checklist\n\n"
        "- [ ] Replace the sample workload with representative requests.\n"
        "- [ ] Pin model, runtime, environment and service commands.\n"
        "- [ ] Set a service-level objective and claim threshold before testing.\n"
        "- [ ] Run `python3 refresh_bindings.py` after replacing placeholders and before collecting evidence.\n"
        "- [ ] Collect at least three passing and failing boundary confirmations.\n"
        "- [ ] Keep confirmation files distinct and preserve open-loop timestamps.\n"
        "- [ ] Capture positive and negative Arm execution profiles separately.\n"
        "- [ ] Bind parser-ready profiler reports to the treatment identities.\n"
        "- [ ] Collect raw HTTP quality responses from the same labeled dataset.\n"
        "- [ ] Rerun `python3 refresh_bindings.py` after profiler capture to bind report hashes.\n"
        "- [ ] Run `armproof seal armproof.json` after collection.\n"
        "- [ ] If the contract changes again, rerun `python3 refresh_bindings.py`.\n"
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
        "Edit the workload, identity sources, service commands, protocol rates, "
        "and claim limits first. `python3 refresh_bindings.py` creates the evidence "
        "directories, copies the templates and source files, and recalculates every "
        "embedded digest.\n\n"
        "Collect each lane and boundary three times with `armproof capacity`. For "
        "each run, copy its `requests-rps-<rate>.jsonl` file to the corresponding "
        "`evidence/requests/<lane>-<pass-or-fail>-<1-3>.jsonl` path shown above. "
        "Run `armproof quality` once against each lane and copy each "
        "`quality-samples.jsonl` to `evidence/quality/<lane>-samples.jsonl`. "
        "Capture each service under representative load with `perf record -e "
        "cycles:P -g -p <pid> -- sleep 60`, then render parser-ready reports with "
        "`perf report --stdio` into `evidence/baseline.perf` and "
        "`evidence/treatment.perf`. Rerun `python3 refresh_bindings.py` to hash "
        "those reports, then run:\n\n"
        "```bash\n"
        "armproof seal armproof.json\n"
        "armproof ci armproof.json\n"
        "```\n\n"
        "The exact flags are listed by `armproof capacity --help` and `armproof quality --help`; "
        "the generated `collection-plan.json` is the machine-readable checklist. "
        "A complete passing parser example is executable under `examples/http-slo/` "
        "in the ArmProof repository and is explicitly labeled synthetic.\n",
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
        "before collecting evidence, then run `python3 refresh_bindings.py` to "
        "update every embedded identity and workflow digest. The `templates/` directory contains exact "
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
            "refresh_bindings.py",
            "ADOPTION_CHECKLIST.md",
            "EVIDENCE_LAYOUT.md",
            "README.md",
            ".github/workflows/armproof.yml",
        )
    )
