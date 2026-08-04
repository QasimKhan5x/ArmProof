# SurgeDesk + ArmProof

## Hackathon Submission Facts

- **Challenge track:** Cloud AI.
- **What was built:** SurgeDesk, a human-confirmed banking-support inference
  application, and ArmProof, its reusable fail-closed optimization release gate.
- **Arm target:** CPU-only AWS Graviton4 (`c8g.4xlarge`) using Arm KleidiAI
  through ONNX Runtime GenAI.
- **Optimization work:** BF16-to-INT4 migration plus a matched INT4
  KleidiAI-disabled/enabled control, measured for artifact size, memory,
  direct inference speed, fixed-SLO capacity, quality and executed Arm
  callchains using both Linux perf and native Arm Performix Code Hotspots.
- **Challenge-period confirmation:** the submitted ArmProof and SurgeDesk work
  was created and meaningfully developed from July 29 through August 4, 2026,
  within the [official June 10 through August 14, 2026 submission period](https://arm-ai-optimization-challenge.devpost.com/rules).
  The public Git history preserves the implementation, evidence and release dates.
- **Judge access:** source, raw evidence, setup instructions, tests, screenshots,
  live demo and technical report are public from this repository.

SurgeDesk is a human-confirmed banking-support triage application that shows
what a measured Arm optimization changes in a real cloud workflow. During a
measured support workload, the same Phi-4 Mini INT4 service on the same AWS
Graviton4 instance sustains **at least 2x more mixed traffic** with KleidiAI
enabled while remaining under its 10-second p95 objective. The tested passing
and failing boundaries come from five 500-second confirmations per rate.

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
- can be recomputed from pinned evidence, artifacts and commands.

The reference path migrates Phi-4 Mini from PyTorch BF16 to INT4 ONNX Runtime
GenAI with KleidiAI on AWS Graviton4. Existing experiments have already shown:

- 35.92% smaller INT4 artifacts than BF16;
- 55.34% lower peak PSS and 59.66% lower time-weighted PSS;
- 1.72x to 2.59x end-to-end speedup from KleidiAI enabled versus disabled in
  the identical INT4 model and runtime;
- 20/24 versus 19/24 quality results; and
- `kai_*` callchains only in the enabled treatment.
- Arm Performix measured 67.02% `kai_*` function samples in the enabled
  treatment and 0% disabled. Linux perf separately attributed 68.53% of cycles
  to the KleidiAI callchain.

The long-window audit exposes every boundary result. The preregistered exact
`2.0x-2.5x` bracket was rejected because the optimized `0.60 r/s` probe passed
one of five windows. The optimized service passed all five windows at `0.56 r/s`, while the
baseline failed all five at `0.28 r/s`. Therefore the sustainable-capacity
improvement supports a separate, narrower claim of at least
`0.56 / 0.28 = 2.0x`.

## Run The Product Demo

```bash
python3.12 scripts/build_surgedesk_demo.py --verify
python3.12 scripts/serve_surgedesk.py --port 8765
```

Open `http://127.0.0.1:8765/surgedesk/`. The three-step judge path is:

1. Send a support request through the human-confirmed triage workflow.
2. Hand the deployment to the capacity audit and check two matched live Arm
   lanes without treating the short request check as a benchmark.
3. Re-verify the 4,200 sustained outcomes, inspect all twenty long windows, and
   open the Arm execution proof.

Each view has a stable URL: `#triage`, `#surge`, and `#proof`. The tabs support
Left/Right Arrow navigation, and every evidence table becomes a labeled card
list on narrow screens.

Recorded mode never simulates live inference or claims autonomous routing.
Fine-grained 77-class accuracy is 46.49%, so human confirmation remains a
visible product requirement. To record a real Graviton request, tunnel the
measured service locally and start the gateway with:

```bash
python3.12 scripts/serve_surgedesk.py --port 8765 \
  --baseline-endpoint http://127.0.0.1:18001/infer \
  --optimized-endpoint http://127.0.0.1:18002/infer
```

## Product Workflow

```text
optimization PR + contract + raw evidence
              |
              v
verify two SHA-256 ledgers, sustained archive, native Performix archive and workload identity
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

The reference command verifies 69 checksummed files in the sustained archive
and 35 in the native Arm Performix bundle, re-derives 4,200 request outcomes, binds them
to the declared identities, and writes `decision.json`, `verification.json`
and an offline report. Exit `0` approves, exit `2` blocks on a failed or
unknown required claim, and exit `1` identifies invalid evidence.

Demonstrate the trust boundary without altering repository evidence:

```bash
python3.12 scripts/demo_release_gate.py
```

It passes all nine claims from the sustained archive, then alters a temporary
archive copy and shows the release blocked before metric derivation.

Use the same config in GitHub Actions:

```yaml
- uses: QasimKhan5x/ArmProof@v0.7.0
  with:
    config: armproof.json
    output: build/armproof-report
    contract-sha256: 3dea0ec2062275181902907d011d27d2b83b11b3ea2e9f8ed5cbce38ede9ff0c
```

Protect the workflow and contract with `CODEOWNERS` and branch rules. The
Action checks the preregistered contract digest before it reads any evidence.

## Scaffold Another Arm Service

Create a runtime-neutral, fail-closed starter for a bounded HTTP classification
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
collection plan, adoption checklist, `armproof.json` and GitHub workflow. Its
built-in quality profile uses exact-label classification; other tasks can add
an evidence adapter through the documented plugin interface. It
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

The canonical sustained bundle contains 69 checksummed files and the native
Performix bundle contains 35. Both verify after relocation. Browser tests cover
the complete SurgeDesk workflow plus ArmProof report layouts down to 320 pixels.

The reference gate also verifies a SHA-256 locked Arm Performix bundle with 35 checksummed files,
recomputes matched Code Hotspots attribution from its native ZIP exports and
blocks if either run is missing, mismatched or contradicts Linux perf.

SurgeDesk verifies the SHA-256 locked `EXP-2026-009` sustained archive and
derives the conservative public capacity claim from its recorded confirmation
rows. Its trial matrix shows every passing, failing, and mixed boundary result.

For a runtime-neutral HTTP-classification starting point, the executable
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
"Arm certified." The 4.9 GB reference model is not stored in Git; the sustained
archive preserves the model digest computed by the evidence producer, while
the live service hashes its local model files at startup. ArmProof detects
later evidence changes and inconsistent identities but does not remotely
attest the original AWS host.
