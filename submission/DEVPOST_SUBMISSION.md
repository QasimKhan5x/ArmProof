# Copy-Ready Devpost Submission

## Project Details

**Project name:** SurgeDesk + ArmProof

**Tagline:** At least twice the AI request capacity on one Graviton server, backed by proof that rejects unsupported claims.

**Track:** Cloud AI

**Source code:** https://github.com/QasimKhan5x/ArmProof

**Live application:** https://qasimkhan5x.github.io/ArmProof/surgedesk/

**Technical report:** https://qasimkhan5x.github.io/ArmProof/report/

**Release:** https://github.com/QasimKhan5x/ArmProof/releases/tag/v0.6.0

**Video:** ADD THE PUBLIC YOUTUBE OR VIMEO URL AFTER RECORDING

**Built with:** AWS Graviton4, Arm KleidiAI, Arm Performix, ONNX Runtime GenAI,
Phi-4 Mini, Python 3.12, Linux perf, GitHub Actions, BANKING77, JavaScript,
HTML, CSS and Playwright.

**Challenge-period confirmation:** SurgeDesk and ArmProof were created and
meaningfully developed from July 29 through August 4, 2026, within the
[official June 10 through August 14, 2026 submission period](https://arm-ai-optimization-challenge.devpost.com/rules).
The public Git history records the implementation, Arm experiments, evidence
and releases completed during that period.

## Short Description

SurgeDesk is an AI assistant for a bank's customer-support team. It reads a
customer message, suggests the correct support queue and procedure, and asks a
human operator to confirm or correct the route.

We optimized its Phi-4 Mini language model for AWS Graviton4, a cloud server
processor built on Arm technology. On the same server, with the same model and workload, the Arm-optimized version
handled at least twice as much sustained traffic while still answering 95% of
requests in under 10 seconds.

ArmProof is the reusable open-source tool behind that result. It checks the
raw benchmark files, model quality and proof that Arm's optimized code really
ran. If any required proof is missing or changed, ArmProof blocks the software
release.

## Inspiration

Performance projects are often presented as one impressive chart. That chart
may be correct, but it does not show what the improvement means to a user. It
also does not stop a future code change from shipping a slower or untested
configuration.

We wanted to answer two practical questions:

1. What does Arm optimization change for a real cloud application?
2. How can another developer verify a similar claim in their own project?

SurgeDesk answers the first question with a working support workflow. ArmProof
answers the second with a command-line tool and GitHub Action that turn raw
performance evidence into a release decision.

## What It Does

### A Real Support Workflow

SurgeDesk uses the public BANKING77 dataset, which contains realistic banking
support questions. For example, a customer might write, "My card has not
arrived."

Phi-4 Mini identifies the detailed issue and suggests a support procedure. A
small routing guard then chooses one of five operational teams. A human sees
both suggestions and makes the final decision.

On 770 test messages that were not used to build the routing guard, the final
queue was correct 86.75% of the time. Directly turning the language model's
answer into a queue was correct about 74.4% of the time. The guard therefore added
12.34 percentage points of routing accuracy. This quality improvement is an
application feature, not an Arm performance claim.

### A Visible Traffic Surge

The application shows what happens when many customers need help at once. The
unoptimized service starts missing its response-time target. The
Arm-optimized service keeps the queue responsive on the same Graviton4
machine.

The headline is based on a long controlled test, not on an animation in the
web application:

- Without KleidiAI, 0.24 requests per second passed all five long tests.
- With KleidiAI, 0.56 requests per second passed all five long tests.
- Without KleidiAI, the next tested rate, 0.28 requests per second, failed all
  five tests.

This proves that the optimized service supports at least twice the sustainable
traffic: 0.56 is twice 0.28. The two passing points are 2.33 times apart, but
we do not claim that 2.33x is the exact maximum capacity.

Each long test ran for 500 seconds. In total, ArmProof checks 4,200 recorded
request results across 20 long test windows.

### A Release Gate Other Developers Can Use

ArmProof verifies the evidence before approving an optimized deployment. It:

- checks that benchmark files have not been changed;
- recalculates the results from the raw request records;
- confirms the model, runtime, workload and server configuration;
- checks that model quality stayed within the declared limit;
- checks matched Linux perf and native Arm Performix evidence showing that
  Arm KleidiAI code executed; and
- returns pass, fail or unknown for every required claim.

Missing proof does not count as success. A failed or unknown required check
blocks the release. ArmProof produces a machine-readable decision, a visual
offline report, a pinned deployment recipe and a GitHub pull-request check.

## What We Optimized

We made three separate comparisons so that each result has a clear cause.

### 1. A Smaller Model

We moved Phi-4 Mini from a 16-bit format called BF16 to a 4-bit format called
INT4. We served the compressed model with ONNX Runtime GenAI, software for
running generative AI models. Fewer bits make the model smaller and reduce the
memory needed to serve it.

Compared with the BF16 version:

- the model files were 35.92% smaller;
- peak process memory was 55.34% lower; and
- memory use over the full run was 59.66% lower.

### 2. Faster Execution With Arm KleidiAI

KleidiAI is Arm's library of optimized mathematical building blocks for AI.
To isolate its effect, we compared two otherwise identical
INT4 services. They used the same model files, ONNX Runtime build, API, 16 CPU
threads, workload, Graviton4 instance and response-time target. The only
intended difference was whether Arm KleidiAI was enabled.

Across four model-input shapes, enabling KleidiAI made execution 1.72 to 2.59
times faster. Linux profiling showed that 68.53% of sampled CPU cycles in the
optimized run passed through KleidiAI matrix-multiplication code, versus 0% in
the control.

We then repeated the positive/negative test with Arm Performix 1.20 Code
Hotspots. From its native profile exports, ArmProof measured 67.02% of
function samples in `kai_*` code when KleidiAI was enabled and 0% when it was
disabled. Performix also exposed the Arm I8MM matrix-kernel family that ran.
Its result was only 1.51 percentage points from the separate Linux perf result.
These tools count different things, so we do not present the percentages as
identical metrics; they independently agree that the optimized Arm path ran.

### 3. More Useful Server Capacity

A faster individual request matters only if the whole service handles more
traffic reliably. We therefore sent requests at fixed rates and required 95%
of responses to finish within 10 seconds.

The optimized service passed every 0.56-request-per-second test. The control
failed every 0.28-request-per-second test. This establishes the conservative
"at least 2x" capacity result on the same server.

We originally hoped to claim an exact 2.5x improvement. The long test did not
support that statement because one higher-load run narrowly passed. ArmProof
rejected the exact 2.5x claim, kept the failed result visible and released only
the lower bound supported by every test.

## How We Built It

1. We fixed the model, software versions, workload, server type and test rules
   before accepting a result.
2. We created two matched INT4 deployments: KleidiAI disabled and KleidiAI
   enabled.
3. We exposed both deployments through the same HTTP API.
4. We measured model speed, memory, quality and sustained service traffic.
5. We tested both versions on the same 770 BANKING77 quality examples. Accuracy
   changed by less than one percentage point, and every response followed the
   required JSON format.
6. We recorded matched Linux perf and native Arm Performix profiles in
   separate runs so profiling overhead could not distort the traffic result.
7. ArmProof checks the Performix archive, opens both native Code Hotspots
   exports and recalculates the `kai_*` sample shares during every reference CI
   run. Missing or contradictory profiles block the release.
8. We stored raw evidence with SHA-256 checksums, which work like fingerprints
   for files. Changing one file changes its fingerprint and blocks approval.
9. We built SurgeDesk and the GitHub Action on the same ArmProof verification
   engine, so the application cannot approve itself by editing displayed data.

## Challenges We Faced

The hardest part was not getting the model to run. It was proving why it ran
better.

Our first memory experiment used the wrong measurement. It counted memory that
the operating system had mapped but did not prove that the model data was
actually resident in memory. We kept that failed experiment, corrected the
method and measured process memory throughout inference.

Capacity testing also required more than comparing two requests-per-second
numbers. We used the same response-time target, fixed arrival rates, known
passing and failing rates, and five long confirmations for each boundary. We
also required quality to pass before a speed claim could pass.

Finally, installing KleidiAI was not enough to prove it caused the gain. We
required profiler records from both configurations: positive evidence in the
optimized version and negative evidence in the control. Arm Performix's CPU
Microarchitecture and Instruction Mix recipes require at least three exposed
hardware counters, while this cloud VM exposed two. We preserved those
readiness failures instead of claiming those reports. Code Hotspots was
supported and completed successfully for the matched causal comparison.

## Accomplishments

- At least 2x higher sustainable AI traffic on the same Graviton4 server.
- A 2.33x difference between the two rates that passed every long test.
- 1.72x to 2.59x faster execution with KleidiAI across four input shapes.
- 35.92% smaller model files and more than 55% lower peak memory after the
  INT4 migration.
- Less than one percentage point of model-quality change and 100% structurally
  valid output across 770 test messages.
- Independent Linux perf and Arm Performix evidence that KleidiAI executed in
  the optimized service and did not execute in the control.
- A release-blocking native Performix importer with archive, checksum,
  treatment, target and contradiction checks.
- A deliberate rejection of our original, stronger 2.5x claim.
- A reusable Python command-line tool, GitHub Action, public data formats,
  benchmark templates, deployment recipe and offline report.
- Automated testing on native Arm64, x86 and desktop/mobile browsers.
- A one-command starter project for another HTTP inference service.
- A tested llama.cpp example showing that ArmProof is not limited to Phi-4 or
  ONNX Runtime. This is a compatibility example, not a performance claim.

## What We Learned

Model compression, Arm acceleration and server capacity are different results.
They need different comparisons:

- BF16 versus INT4 explains the file-size and memory savings.
- KleidiAI disabled versus enabled explains the Arm-specific speedup.
- Fixed-rate traffic tests explain how many requests the service can support.

We also learned that a polished report is not proof by itself. ArmProof starts
from raw evidence, recalculates the comparison, verifies the declared
configuration and only then creates the decision used by the report and GitHub
Action.

Most importantly, performance is easier to understand when it changes a real
user outcome. In SurgeDesk, twice the sustainable capacity means the support
queue remains responsive during a surge without buying a larger server.

## Why It Matters To The Arm Community

Developers can reuse the measured Phi-4 Mini, ONNX Runtime GenAI and KleidiAI
reference directly. They can also use ArmProof with a different model or
runtime.

The repository includes:

- a common HTTP interface for inference services;
- traffic and quality test tools;
- matched baseline and optimized deployment templates;
- public evidence and decision formats;
- file-integrity verification;
- Arm execution checks using native Linux perf and Arm Performix data;
- a plain-English Performix tutorial and reusable native-export validator;
- examples of pass, fail and missing evidence;
- a GitHub Action and offline report;
- a pinned Graviton deployment recipe;
- a one-command adoption scaffold; and
- a tested llama.cpp bridge.

A developer can fork the project, connect their own service, choose the quality
and performance requirements that matter to them, and make unsupported
optimization claims fail automatically. No hosted ArmProof service is needed.

## Why It Should Win

This project does not simply place an AI application on an Arm server. It
compresses a real model, isolates and measures an Arm-specific acceleration
path, validates quality, measures sustained cloud capacity and turns the
result into reusable developer tooling.

The result is simple to see: the same Graviton4 server handles at least twice
the sustained AI traffic. The engineering behind that result is inspectable,
reproducible and honest enough to reject a stronger number when the evidence
does not support it.

SurgeDesk shows why the optimization matters. ArmProof helps the next Arm
developer prove their own work.

## What's Next

- Turn the llama.cpp compatibility example into a fully measured adapter.
- Add vLLM and more ONNX Runtime examples.
- Validate the same workflow on Google Axion and Microsoft Cobalt.
- Add ready-made templates for text generation, vision and speech services.

## Setup And Validation

The web demo and accepted evidence run locally; judges do not need an AWS
account.

```bash
git clone https://github.com/QasimKhan5x/ArmProof.git
cd ArmProof
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
make check
.venv/bin/armproof ci examples/armproof-reference/armproof.json
python3.12 scripts/demo_release_gate.py
python3.12 scripts/serve_surgedesk.py --port 8765
```

Open `http://127.0.0.1:8765/surgedesk/`.

The complete Graviton service recipe, pinned software versions, matched
deployment generator and benchmark runner are under `examples/phi4-graviton/`
and `deploy/`.

## Open Source And Data

The project is MIT licensed. BANKING77 is used under CC BY 4.0 and is credited
in `THIRD_PARTY_NOTICES.md`. Model weights are not redistributed.
