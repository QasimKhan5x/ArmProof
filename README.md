# ArmProof

ArmProof is a fail-closed CI release gate for Arm AI optimization pull
requests. It approves a deployment only when the submitted evidence shows that
the change:

- preserves the workload's declared quality contract;
- improves its declared cloud-serving objective;
- executes the required Arm acceleration path; and
- can be reproduced from pinned artifacts and commands.

The reference path migrates Phi-4 Mini from PyTorch BF16 to INT4 ONNX Runtime
GenAI with KleidiAI on AWS Graviton4. Existing experiments have already shown:

- 35.92% smaller INT4 artifacts than BF16;
- 55.34% lower peak PSS and 59.66% lower time-weighted PSS;
- 1.72x to 2.59x end-to-end speedup from KleidiAI enabled versus disabled in
  the identical INT4 model and runtime;
- 20/24 versus 19/24 quality results; and
- `kai_*` callchains only in the enabled treatment.

The decisive service gate then measured 3.0x, 2.5x and 3.0x sustainable
capacity across short, long and mixed traffic under the same 10-second p95
SLO. A fresh `c8g.4xlarge` reproduced all three ratios exactly.

## Product Workflow

```text
optimization PR + armproof.json
              |
              v
matched baseline/treatment runs on Graviton
              |
              v
fail-closed claim ledger
              |
              +--> GitHub Check: pass/fail
              +--> interactive evidence report
              +--> reproducible deployment manifest
```

Evaluate the accepted reference from one config:

```bash
python3.12 -m pip install -e .
armproof ci examples/armproof-reference/armproof.json
```

The command writes `decision.json`, normalized inputs and an offline interactive
report. Exit `0` approves, exit `2` blocks on a failed or unknown required
claim, and exit `1` identifies invalid input or execution failure.

Use the same config in GitHub Actions:

```yaml
- uses: QasimKhan5x/VerifyLane@v0.1.0
  with:
    config: armproof.json
    output: build/armproof-report
```

## Current Build

The repository contains strict contracts, the common Phi-4 service, fixed-SLO
load harness, quality evaluator, Arm attribution evidence, fail-closed policy
engine, GitHub Action, offline report and exact passing deployment.

```bash
make check
PYTHONPATH=src python3.12 -m armproof.cli ci \
  examples/armproof-reference/armproof.json
```

Both accepted cloud bundles contain 141 checksummed files and verify after
relocation. Browser tests cover desktop, tablet and 320-pixel mobile layouts.

## Start Here

- Current state: [`STATUS.md`](STATUS.md)
- Five-minute quickstart: [`docs/QUICKSTART.md`](docs/QUICKSTART.md)
- Agent rules: [`AGENTS.md`](AGENTS.md)
- Product specification: [`docs/PRODUCT_SPEC.md`](docs/PRODUCT_SPEC.md)
- Established evidence: [`docs/ESTABLISHED_EVIDENCE.md`](docs/ESTABLISHED_EVIDENCE.md)
- Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Requirements: [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md)
- Implementation plan: [`tasks/plan.md`](tasks/plan.md)
- Project routing map: [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md)

## Claim Boundary

ArmProof is not an Arm certification authority and does not prove universal
model quality or optimality. It evaluates a declared contract for a pinned
model, workload, runtime and machine. User-facing copy must say "verified by
ArmProof," never "Arm certified."
