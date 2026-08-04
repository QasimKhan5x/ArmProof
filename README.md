# SurgeDesk + ArmProof

SurgeDesk is a human-confirmed banking-support triage application that shows
what a measured Arm optimization changes in a real cloud workflow. During a
recorded support surge, the same Phi-4 Mini INT4 service on the same AWS
Graviton4 instance sustains **at least 2x more mixed traffic** with KleidiAI
enabled while remaining under its 10-second p95 objective. The tested passing
points are `0.24` versus `0.56 r/s`, a 2.33x ratio, across five 500-second
confirmations per boundary.

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

Short discovery runs initially suggested 2.5x-3.0x capacity. The decisive
long-window audit correctly rejected that exact bracket: `0.60 r/s` passed one
of five optimized windows. It still established the conservative result used
publicly: baseline `0.24 r/s` and optimized `0.56 r/s` passed all five windows,
while baseline `0.28 r/s` failed all five. Therefore the sustainable-capacity
improvement is at least `0.56 / 0.28 = 2.0x`; it is not labeled an exact maximum.

## Run The Product Demo

```bash
python3.12 scripts/build_surgedesk_demo.py --verify
python3.12 scripts/serve_surgedesk.py --port 8765
```

Open `http://127.0.0.1:8765/surgedesk/`. The three-step judge path is:

1. Use **Guard intervention** and **Human correction** to inspect both sides of
   the human-confirmed BANKING77 routing boundary.
2. Inspect the equal-load customer outcome, then reveal the long-window lower bound.
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
optimization PR + contract + raw evidence
              |
              v
verify two SHA-256 ledgers, sustained archive and workload identity
              |
              v
re-derive raw request metrics + bind treatment identities
              |
              v
fail-closed versioned claim ledger
              |
              +--> GitHub Check: pass/fail
              +--> interactive evidence report
              +--> reproducible deployment manifest
```

Evaluate the accepted reference from one config:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/armproof ci examples/armproof-reference/armproof.json
```

The reference command verifies 282 files across the primary and reproduction bundles,
derives the normalized comparison from request and quality evidence, binds it
to the declared identities, and writes `decision.json`, `verification.json`
and an offline report. Exit `0` approves, exit `2` blocks on a failed or
unknown required claim, and exit `1` identifies invalid evidence.

Demonstrate the trust boundary without altering repository evidence:

```bash
python3.12 scripts/demo_release_gate.py
```

It first passes all eight claims, then changes one digest in a temporary ledger
and shows the release blocked before policy evaluation.

Use the same config in GitHub Actions:

```yaml
- uses: QasimKhan5x/ArmProof@v0.5.1
  with:
    config: armproof.json
    output: build/armproof-report
```

## Scaffold Another Arm Service

Create a runtime-neutral, fail-closed starter for any bounded HTTP inference
endpoint:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/armproof init \
  --endpoint http://127.0.0.1:8000/infer \
  --output my-arm-service
cd my-arm-service
```

The command creates a versioned contract, workload template, identity sources,
collection plan, adoption checklist, `armproof.json` and GitHub workflow. It
does **not** generate passing evidence. `armproof ci armproof.json` fails closed
until real request rows, profiler output, observed identities and a SHA-256
ledger replace the templates. The complete executable evidence shape is in
[`examples/http-slo/`](examples/http-slo/).

## Current Build

The repository contains strict contracts, the common Phi-4 service, fixed-SLO
load harness, quality evaluator, Arm attribution evidence, fail-closed policy
engine, GitHub Action, offline report and pinned conservative deployment.

```bash
make check
PYTHONPATH=src python3.12 -m armproof.cli ci \
  examples/armproof-reference/armproof.json
```

The primary and fresh-instance confirmation bundles each contain 141 checksummed files
and verify after relocation. Browser tests cover the complete SurgeDesk workflow plus ArmProof
report layouts down to 320 pixels.

SurgeDesk additionally verifies the SHA-256 locked `EXP-2026-009` sustained
archive and derives the conservative public capacity claim from its recorded
confirmation rows. The failed original 2.5x bracket remains visible in the app.

For a runtime-neutral starting point, the executable
[`examples/http-slo/`](examples/http-slo/) kit generates a complete raw-evidence
layout, observed identities, contract, report and Action template. External
adapters are discovered through Python entry points and listed by
`armproof adapters`.

The tested [`examples/llama-cpp-http-slo/`](examples/llama-cpp-http-slo/)
bridge adapts llama.cpp's OpenAI-compatible endpoint to the same bounded
`/infer` contract. Its real Qwen2.5 smoke proves runtime compatibility only;
it intentionally publishes no performance or optimization result.

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

ArmProof is not an Arm certification authority and its repository checksum
ledgers are integrity controls, not independent attestation of the evidence
producer. It evaluates a declared contract for a pinned model, workload,
runtime and machine. User-facing copy must say "verified by ArmProof," never
"Arm certified."
