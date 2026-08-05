# SurgeDesk + ArmProof

SurgeDesk is a banking-support application running on a CPU-only AWS Graviton4
server. Phi-4 Mini suggests the intent, SurgeDesk selects the matching support
procedure, and a person chooses the final queue.

The application starts on its standard service. ArmProof checks the measured
performance, output quality and Arm execution before SurgeDesk can switch to the
KleidiAI-optimized service. Each ticket records which service handled it.

**Challenge track:** Cloud AI, Arm Create AI Optimization Challenge.

## Measured Result

The KleidiAI-optimized service handled **at least twice the sustained traffic**
on the same 16-core `c8g.4xlarge`. A test window passes only when 95% of requests
finish within ten seconds, no request errors occur, and at least 95% of the
offered traffic is completed.

| Preregistered confirmation | Rate | Five 500-second windows |
|---|---:|---:|
| KleidiAI disabled control | 0.28 requests/s | 5 failed |
| KleidiAI enabled treatment | 0.56 requests/s | 5 passed |

The standard service fails at 0.28 requests per second, so its sustainable rate
is below 0.28. The optimized service passes at 0.56, so its sustainable rate is
at least 0.56. That establishes the conservative lower bound
`0.56 / 0.28 = at least 2.0x`.

The two service configurations use the same Phi-4 Mini INT4 files, ONNX Runtime
build, 16 threads, workload, server and response-time rule; their only changed
runtime setting enables KleidiAI. The final capacity test intentionally offers
each service its frozen boundary rate, 0.28 and 0.56 requests per second, to
establish the conservative lower bound. Git commit `ab22cc0` contains the exact final plan, and its commit time
precedes the instance-launch time recorded in the experiment metadata. That is
a reproducible chronology check, not independent AWS attestation.

Earlier tests located the standard service between 0.24 and 0.28 requests per
second. The optimized service passed at 0.56, while 0.60 produced mixed results.
Those observations selected the two final rates. EXP-2026-014 then tested only
those committed rates and required every response to carry the complete model,
runtime, Arm64, thread and treatment identity.

For the release, ArmProof checks:

- 2,100 raw request outcomes from the ten capacity windows;
- 1,540 raw model outputs, 770 from each lane;
- that accuracy and class-balanced F1 change by less than one percentage point;
- that at least 99% of model outputs use the required JSON format; and
- four hash-locked deployment measurement files used to recalculate footprint
  percentages and raw-repetition timing medians; and
- Arm Performix profiles with zero KleidiAI functions in the control and at
  least 50% KleidiAI function samples in the optimized service.

An exploratory supporting test recalculates five raw repetitions for each of
four fixed input shapes and found 1.72x to 2.59x faster direct inference. The
earlier BF16-to-INT4 migration measured 35.92%
smaller model files, 55.34% lower peak proportional set size (PSS) and 59.66%
lower time-weighted PSS, a measure of the process's share of memory over time.
These model-migration results are reported separately from the KleidiAI-only
comparison.
ArmProof recalculates the size and memory percentages from locked aggregate
measurements and the timing medians from raw repetitions in EXP-2026-002;
editing the display summary cannot change the published report.

## Product Workflow

```text
real support message
        |
        v
serving control + sequential optimized shadow -> fresh side-by-side observation
        |
        v
Phi-4 intent -> SurgeDesk procedure + queue guard -> human chooses final queue
        |
        v
verify preregistered capacity + raw quality + native Performix evidence
        |
        v
verify wheel ledger + AWS instance + model + Arm placement + treatment control
        |
        v
switch live traffic -> different request records optimized lane + audit ID
```

The five-queue routing guard was built on 2,310 BANKING77 examples and evaluated
on a disjoint 770-message development holdout. It raised routing accuracy from
74.42% for direct model mapping to 86.75%. A person still selects every final
queue, and this routing feature is separate from the Arm performance result.

## Verify The Reference

Prerequisite: Python 3.12.

```bash
git clone https://github.com/QasimKhan5x/ArmProof.git
cd ArmProof
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/armproof ci examples/armproof-reference/armproof.json
```

The command verifies the archive ledgers, re-derives end-to-end capacity and quality from
raw rows, parses native Arm Performix exports, binds the observed treatment
identities to `confirmed-contract.json`, and writes:

- `decision.json`
- `comparison.json`
- `summary.json`
- `verification.json`
- an offline HTML report

Exit `0` approves every required claim. Exit `2` means at least one required
claim failed or remained unknown. Exit `1` means the evidence or configuration
was invalid.

## Run The Product

```bash
python3.12 scripts/build_surgedesk_demo.py --verify
python3.12 scripts/serve_surgedesk.py --port 8765
```

Open <http://127.0.0.1:8765/surgedesk/>. This local path uses the checked-in
evidence and recorded BANKING77 examples, so judges can inspect the workflow
without AWS credentials or model downloads.

The three views have stable URLs:

- `#triage`: support workflow and human routing decision
- `#surge`: preregistered capacity audit and raw outcomes
- `#proof`: live traffic control, optimization summary and Arm Performix evidence

The full recording uses a real serving-plus-shadow comparison before the route
cutover and a different real Graviton request after it.
The exact commands and expected outputs are in
[`submission/DEMO_SCRIPT.md`](submission/DEMO_SCRIPT.md).

## Reuse ArmProof

ArmProof provides:

- versioned performance, quality and Arm-execution contracts;
- a fixed-rate HTTP load generator;
- hash-locked raw request and raw model-output verification;
- native Arm Performix Code Hotspots parsing;
- model, runtime, workload and environment identity binding;
- an offline report and machine-readable receipt;
- a GitHub Action for pull-request release gates;
- a blocked-by-default starter generated by `armproof init`; and
- a public evidence-adapter interface for other runtimes.

Generate a starter for another bounded HTTP classification service:

```bash
.venv/bin/armproof init \
  --endpoint http://127.0.0.1:8000/infer \
  --output my-arm-service
cd my-arm-service
../.venv/bin/armproof ci armproof.json
```

The 16-file starter includes exact protocol, identity and profiler-manifest
templates as well as the workloads, collection plan and GitHub Action. The
initial check fails until the developer collects real request rows, profiler
output and observed identities. After collection,
`armproof seal armproof.json` creates the deterministic checksum ledger and
`armproof ci armproof.json` evaluates the contract. The executable reference
shape is in [`examples/http-slo/`](examples/http-slo/). The tested
[`examples/llama-cpp-http-slo/`](examples/llama-cpp-http-slo/) adapter confirms
endpoint compatibility; it does not claim a llama.cpp performance result.

Use ArmProof in GitHub Actions:

```yaml
- uses: QasimKhan5x/ArmProof@v0.9.0
  with:
    config: armproof.json
    contract-sha256: REPLACE_WITH_THE_PROTECTED_CONTRACT_DIGEST
```

Protect the workflow and contract with `CODEOWNERS` and branch rules. The
Action checks the contract digest before reading evidence.

## Arm Optimization Details

- **Hardware:** AWS Graviton4, `c8g.4xlarge`, 16 Arm Neoverse V2 cores
- **Model:** `microsoft/Phi-4-mini-instruct-onnx`, pinned revision, CPU INT4
- **Runtime:** pinned ONNX Runtime and ONNX Runtime GenAI Arm64 builds
- **Arm library:** KleidiAI v1.20 through ONNX Runtime
- **Control:** `mlas.disable_kleidiai=1`
- **Treatment:** `mlas.disable_kleidiai=0`
- **Profiler:** Arm Performix 1.20 Code Hotspots, with Linux perf as a separate cycle view
- **Workload:** frozen BANKING77 quality and mixed traffic inputs
- **SLO:** p95 at or below 10 seconds, zero errors, at least 95% delivery

The Performix release gate uses function samples in their native units. Linux
perf cycle attribution is supporting evidence and is not numerically compared
with the Performix percentage.

## Test The Project

```bash
make check
npm ci
npx playwright install chromium
npm run test:logic
npm run test:ui
```

Tests cover policy evaluation, archive derivation, raw-output quality checks,
native Performix parsing, runtime-artifact and IMDSv2 deployment checks,
per-request drift rejection, a real localhost control-to-treatment HTTP flow,
the SurgeDesk workflow, the offline report and responsive layouts down to 320
pixels.

## Repository Map

- [`submission/DEVPOST_SUBMISSION.md`](submission/DEVPOST_SUBMISSION.md): copy-ready submission
- [`submission/DEMO_SCRIPT.md`](submission/DEMO_SCRIPT.md): setup and three-minute recording sequence
- [`submission/JUDGE_GUIDE.md`](submission/JUDGE_GUIDE.md): fastest evaluation path
- [`submission/TECHNICAL_EVIDENCE.md`](submission/TECHNICAL_EVIDENCE.md): claim-to-artifact map
- [`examples/armproof-reference/`](examples/armproof-reference/): release contract and config
- [`ops/experiments/`](ops/experiments/): preregistered experiments
- [`ops/evidence/`](ops/evidence/): accepted and rejected evidence history
- [`examples/phi4-graviton/`](examples/phi4-graviton/): pinned Arm deployment
- [`docs/PERFORMIX.md`](docs/PERFORMIX.md): native Performix collection and interpretation

## Scope And Provenance

ArmProof verifies a declared contract for a pinned model, workload, runtime and
machine. Repository SHA-256 ledgers detect changes after collection; they are
integrity controls rather than independent attestation of the original AWS
host. The live service verifies the pinned wheel ledger, reads its instance type
from AWS IMDSv2, and reports actual CPU affinity. The gateway checks those values
and content-derived model identities before promotion and on every optimized
response. This is deployment validation rather than hardware-backed remote
attestation.

SurgeDesk and ArmProof were created and meaningfully developed from July 29
through August 5, 2026, during the challenge period. The Git history contains
the source changes, preregistered plans, experiment records, and evidence used
by the release.

The project is MIT licensed. BANKING77 is used under CC BY 4.0 and credited in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Model weights are downloaded
from their original source and are not redistributed.
