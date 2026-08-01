# SurgeDesk + ArmProof

SurgeDesk is a human-confirmed banking-support triage application that shows
what a measured Arm optimization changes in a real cloud workflow. During a
recorded support surge, the same Phi-4 Mini INT4 service on the same AWS
Graviton4 instance sustains **3x mixed traffic** with KleidiAI enabled while
remaining under its 10-second p95 objective.

A dependency-free queue guard raises held-out five-destination routing accuracy from
74.42% for direct LLM mapping to **86.75%** while retaining Phi-4 Mini for the
fine-grained intent and procedure suggestion. Every final route remains human
confirmed.

ArmProof is the reusable engine behind the demo. It is a fail-closed CI release
gate that approves an Arm AI deployment only when submitted evidence shows
that the change:

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

## Run The Product Demo

```bash
python3.12 scripts/build_surgedesk_demo.py --verify
python3.12 scripts/serve_surgedesk.py --port 8765
```

Open `http://127.0.0.1:8765/surgedesk/`. The three-step judge path is:

1. Use **Guard intervention** and **Human correction** to inspect both sides of
   the human-confirmed BANKING77 routing boundary.
2. Replay the same raw demand in both treatments, then reveal confirmed capacity.
3. Inspect the Arm execution, quality, reproduction and deployment proof.

Each view has a stable URL: `#triage`, `#surge`, and `#proof`. The tabs support
Left/Right Arrow navigation, and every evidence table becomes a labeled card
list on narrow screens.

Recorded mode never simulates live inference or claims autonomous routing.
Fine-grained 77-class accuracy is 46.49%, so human confirmation remains a
visible product requirement. To record a real Graviton request, tunnel the
measured service locally and start the gateway with:

```bash
SURGEDESK_INFERENCE_ENDPOINT=http://127.0.0.1:8000/infer \
  python3.12 scripts/serve_surgedesk.py --port 8765
```

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
- uses: QasimKhan5x/VerifyLane@v0.2.0
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
relocation. Browser tests cover the complete SurgeDesk workflow plus ArmProof
report layouts down to 320 pixels.

## Start Here

- Devpost submission package: [`submission/README.md`](submission/README.md)
- Three-minute recording script: [`submission/DEMO_SCRIPT.md`](submission/DEMO_SCRIPT.md)
- Judge guide: [`submission/JUDGE_GUIDE.md`](submission/JUDGE_GUIDE.md)
- Current state: [`STATUS.md`](STATUS.md)
- Five-minute quickstart: [`docs/QUICKSTART.md`](docs/QUICKSTART.md)
- Product demo guide: [`docs/SURGEDESK_DEMO.md`](docs/SURGEDESK_DEMO.md)
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
