"""Static text emitted by the HTTP classification adoption scaffold."""

from __future__ import annotations


REFRESH_BINDINGS_SCRIPT = r'''#!/usr/bin/env python3
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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
'''


ADOPTION_CHECKLIST = """# ArmProof HTTP Classification Adoption Checklist

- [ ] Replace the sample workload with representative requests.
- [ ] Pin model, runtime, environment and service commands.
- [ ] Set a service-level objective and claim threshold before testing.
- [ ] Run `python3 refresh_bindings.py` after replacing placeholders and before collecting evidence.
- [ ] Collect at least five passing and failing boundary confirmations with at
      least 100 raw requests in each confirmation.
- [ ] Keep confirmation files distinct and preserve open-loop timestamps.
- [ ] Capture positive and negative Arm execution profiles separately.
- [ ] Bind parser-ready profiler reports to the treatment identities.
- [ ] Collect raw HTTP quality responses from the same labeled dataset.
- [ ] Rerun `python3 refresh_bindings.py` after profiler capture to bind report hashes.
- [ ] Run `armproof seal armproof.json` after collection.
- [ ] If the contract changes again, rerun `python3 refresh_bindings.py`.
- [ ] Run `armproof ci armproof.json`; missing evidence must block.
"""


EVIDENCE_LAYOUT = """# HTTP Classification Evidence Layout

`collection-plan.json` contains these paths as machine-readable JSON. Collect each file from matched baseline and treatment runs; never reuse one confirmation under more than one name.

```text
evidence/
  protocol.json
  identities.json
  baseline.perf
  treatment.perf
  profiles/manifest.json
  quality/baseline-samples.jsonl
  quality/treatment-samples.jsonl
  requests/{baseline,treatment}-{pass,fail}-{1,2,3,4,5}.jsonl
  identity-sources/artifact.ref
  identity-sources/runtime.lock
  identity-sources/environment.json
  identity-sources/workload-manifest.json
  identity-sources/capacity.jsonl
  identity-sources/quality.jsonl
```

Edit the workload, identity sources, service commands, protocol rates, and claim limits first. `python3 refresh_bindings.py` creates the evidence directories, copies the templates and source files, and recalculates every embedded digest.

Collect each lane and boundary five times with `armproof capacity`, retaining at least 100 raw requests per confirmation. For each run, copy its `requests-rps-<rate>.jsonl` file to the corresponding `evidence/requests/<lane>-<pass-or-fail>-<1-5>.jsonl` path shown above. Run `armproof quality` once against each lane and copy each `quality-samples.jsonl` to `evidence/quality/<lane>-samples.jsonl`. Capture each service under representative load with `perf record -e cycles:P -g -p <pid> -- sleep 60`, then render parser-ready reports with `perf report --stdio` into `evidence/baseline.perf` and `evidence/treatment.perf`. Rerun `python3 refresh_bindings.py` to hash those reports, then run:

```bash
armproof seal armproof.json
armproof ci armproof.json
```

The exact flags are listed by `armproof capacity --help` and `armproof quality --help`; the generated `collection-plan.json` is the machine-readable checklist. A complete passing parser example is executable under `examples/http-slo/` in the ArmProof repository and is explicitly labeled synthetic.
"""


def starter_readme(endpoint: str, version: str) -> str:
    return f"""# ArmProof HTTP Classification Starter

Target endpoint: `{endpoint}`

This scaffold intentionally contains no passing evidence. It targets exact-label HTTP classification services. Start with `ADOPTION_CHECKLIST.md`, use the fixed-SLO collector, then place raw files under `evidence/`. Until that evidence is complete and checksum-bound, `armproof ci armproof.json` fails closed.

## Check The Empty Starter

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install git+https://github.com/QasimKhan5x/ArmProof.git@v{version}
.venv/bin/armproof ci armproof.json
```

The last command must fail because the starter has no measurements. Follow `EVIDENCE_LAYOUT.md` and `ADOPTION_CHECKLIST.md`. After collection:

```bash
.venv/bin/armproof seal armproof.json
.venv/bin/armproof ci armproof.json
```

Replace both workload templates and the identity-source placeholders before collecting evidence, then run `python3 refresh_bindings.py` to update every embedded identity and workflow digest. The `templates/` directory contains exact parser-ready JSON shapes; the collection plan names every required output.

Before production, ensure the generated workflow uses the released Action's full commit SHA. Release tooling can pass that commit directly to `create_scaffold`; no future commit is embedded in this package.

See the complete executable shape in the upstream `examples/http-slo/` directory.
"""
