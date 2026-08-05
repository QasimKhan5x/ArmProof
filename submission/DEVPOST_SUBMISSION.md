# Copy-Ready Devpost Submission

## Project Details

**Project name:** SurgeDesk + ArmProof

**Tagline:** SurgeDesk uses KleidiAI to handle at least twice the sustained banking-support traffic on the same Graviton4 server.

**Track:** Cloud AI

**Source code:** https://github.com/QasimKhan5x/ArmProof

**Interactive evidence explorer:** https://qasimkhan5x.github.io/ArmProof/surgedesk/

**Technical report:** https://qasimkhan5x.github.io/ArmProof/report/

**Release:** https://github.com/QasimKhan5x/ArmProof/releases/tag/v0.8.2

**Video:** ADD THE PUBLIC YOUTUBE OR VIMEO URL AFTER RECORDING

**Built with:** AWS Graviton4, Arm KleidiAI, Arm Performix, ONNX Runtime GenAI,
Phi-4 Mini, Python 3.12, Linux perf, GitHub Actions, BANKING77, JavaScript,
HTML, CSS and Playwright.

## Short Description

SurgeDesk is a banking-support application. A support agent enters a customer
message, receives an AI-classified intent and the application's matching
procedure, chooses the final queue, and routes the ticket.

The application begins on the standard Phi-4 Mini INT4 service with KleidiAI
off. It recalculates a Graviton4 capacity test and checks an Arm Performix
profile showing which code ran. Once those checks pass, the same interface
activates the optimized service. The same support message is then sent again;
its new request ID, timestamp and runtime receipt visibly come back through the
KleidiAI-enabled service.

The public GitHub Pages build lets judges inspect the application and its
checked-in evidence without AWS access. The video uses the local gateway and
two live Graviton endpoints for the control-to-treatment activation.

On the same `c8g.4xlarge`, the optimized service sustained 0.56 requests per
second in five 500-second windows. The control failed the same ten-second p95
objective in all five windows at 0.28 requests per second. This establishes a
conservative lower bound of at least twice the sustained request rate.

ArmProof is the reusable open-source component behind the release. It verifies
raw request records, raw model outputs, treatment identities, quality limits
and native Arm profiler exports before a deployment can be approved.

## The Problem

An AI service can look faster in a short test and still fail under sustained
traffic, damage output quality or miss the intended optimized code path. This
project connects those three checks to a real deployment action:

1. SurgeDesk shows the operational effect of the optimization in a live support workflow.
2. ArmProof turns the measurements into a versioned release contract, CLI check and GitHub Action.

## What The Application Does

### Live Support Triage

The demo uses realistic banking questions from BANKING77. Phi-4 Mini proposes a
fine-grained intent, and SurgeDesk selects the matching support procedure. A
small local routing guard proposes one of five operational queues, and the
support agent chooses the final queue.

The routing guard was built on 2,310 examples and evaluated on a disjoint
770-message development holdout. It improved five-queue routing accuracy from
74.42% for direct model mapping to 86.75%. This is an application-quality
feature; it is separate from the Arm performance claim and every final route
still requires a person.

### Evidence-Driven Deployment

The live gateway starts on the control lane. The platform operator then runs
the current ArmProof audit from the application. The audit:

- verifies the capacity archive and its internal SHA-256 ledger;
- re-derives 2,100 individual request outcomes from ten long windows;
- re-evaluates 1,540 raw model outputs, 770 from each treatment;
- recalculates size and memory percentages from locked aggregate measurements
  and direct-speed medians from raw repetitions in four hash-locked files;
- checks that the model, runtime, workload, server shape, SLO and thread count match;
- evaluates ten required quality, capacity, evidence-volume and Arm-execution claims; and
- reads the native Arm Performix Code Hotspots exports directly.

After the audit passes, activation probes both live services again. Their source
model fingerprint, ONNX Runtime GenAI version, Arm64 architecture, 16-thread
shape and KleidiAI controls must match the audited deployment. The route then
switches to the treatment, and the next real request carries the release audit
ID in the application's audit trail.

## What We Optimized

### Model Footprint

We migrated the reference model from BF16 to the public Phi-4 Mini INT4 ONNX
artifact and served it with ONNX Runtime GenAI. The migration measurements
recorded:

- 35.92% smaller model files;
- 55.34% lower peak proportional set size (PSS), which estimates the process's
  share of memory also used by other processes; and
- 59.66% lower time-weighted PSS.

The current release keeps these migration results separate from the KleidiAI
control experiment because quantization and Arm kernel dispatch answer different
questions.

### Arm Execution

For the KleidiAI experiment, both services use the same INT4 files, ONNX Runtime
build, API, workload, 16 threads and Graviton4 server. The declared treatment
control is `mlas.disable_kleidiai`: `1` for the control and `0` for the treatment.

An exploratory fixed-shape test covered batch/prompt shapes `(1,128)`,
`(1,512)`, `(4,128)` and `(4,512)`. ArmProof recalculates each median from five
raw repetitions and reports a 1.72 to 2.59 times speed range as supporting
evidence, separate from the confirmed capacity result. Arm Performix sampled
the running code in a matched control and optimized profile. The control must contain
zero KleidiAI-prefixed (`kai_*`) functions, the treatment must contain at least
50%, and each profile must contain at least 100,000 function samples. The native export also
names the Neoverse I8MM matrix kernel that executed.

Linux perf provides a second view using sampled cycles. ArmProof reports the
Performix function-sample share and Linux perf cycle attribution separately
because the denominators are different.

The release report calculates these supporting size, memory and direct-speed
figures from the locked EXP-2026-002 measurement files.

### Sustainable Server Capacity

The HTTP client sends requests on a fixed schedule instead of waiting for each
response. A window passes when 95% of responses finish within ten seconds, no
request errors occur, and at least 95% of the scheduled traffic completes. Each
confirmation lasts 500 seconds.

Latency begins at the scheduled send time, so client dispatch delay is included.
Responses that finish after the 500-second window plus a ten-second SLO drain
do not count as delivered. Every successful response also carries the source-model,
runtime, Arm64, thread and KleidiAI identity that ArmProof checks against the
release.

Discovery found the standard service passing at 0.24 requests per second and
failing at 0.28. The optimized service passed at 0.56, while 0.60 produced mixed
results and was not used as an exact upper boundary. Before launching the final
confirmation instance, we committed a contract with one possible success:

- every one of five control windows at 0.28 requests per second must fail; and
- every one of five treatment windows at 0.56 requests per second must pass.

Any opposite outcome, missing request, quality breach or identity mismatch
rejects the public claim. The final run met every condition, so the release
publishes `0.56 / 0.28 = at least 2.0x` sustained capacity. No rate or threshold
was selected after seeing the confirmation result.

EXP-2026-014 ran those unchanged rates and rules with the complete response
identity required by the release contract. The repository retains every earlier
attempt in its evidence history; the public capacity claim uses only this final
confirmation.

## How We Built It

1. We pinned the model revisions, ONNX Runtime and ONNX Runtime GenAI commits,
   KleidiAI version, AWS instance type, workloads and quality limits.
2. We generated two model overlays whose only intended runtime change is the
   KleidiAI control.
3. We ran the same bounded HTTP service on CPU-only AWS Graviton4.
4. We collected direct inference, memory, fixed-rate capacity, quality, Linux
   perf and Arm Performix evidence in separately scoped experiments.
5. We bound the final capacity and Performix rules to Git commits whose times
   precede the AWS launch times recorded in the experiment metadata. This makes
   the chronology inspectable, but we do not present it as independent AWS
   attestation.
6. We wrote adapters that reopen the immutable archives and derive decisions
   from raw rows and native profiler exports.
7. We connected that decision to a stateful gateway: control route, fresh
   audit, identity-bound activation, optimized route.
8. We packaged the verification path as a Python CLI, offline report and GitHub Action.

## Why Arm Matters

This project targets CPU-only cloud inference on AWS Graviton4 and uses Arm's
KleidiAI kernels through ONNX Runtime GenAI. The matched control isolates the
effect of that Arm path, while Arm Performix identifies the `kai_*` functions
and Neoverse I8MM kernel family observed during inference.

The result is useful at service level: the same 16-core server accepts at least
twice the sustained request rate under the same latency and quality rules. On
an x86 machine the KleidiAI treatment and the measured Neoverse I8MM path are
absent, so the central experiment and deployment contract do not carry over.

## Reusable Work For Other Developers

ArmProof ships with:

- a public contract format for performance, quality and Arm-execution claims;
- raw-evidence adapters for fixed-SLO HTTP services;
- direct readers for native Arm Performix Code Hotspots exports;
- a fixed-rate load generator and BANKING77 quality evaluator;
- source-model, runtime, workload and environment identity checks;
- a CLI that exits successfully only when every required claim passes;
- an offline HTML report and machine-readable decision;
- a GitHub Action for pull-request release gates;
- `armproof init`, which creates a blocked-by-default 16-file starter with exact protocol, identity and profiler-manifest templates for another HTTP AI service;
- `armproof seal`, which writes a deterministic evidence ledger after collection without approving the result;
- a SurgeDesk handoff that runs the scaffold check and downloads the generated starter as a ZIP;
- a complete Graviton4 deployment recipe; and
- a tested llama.cpp HTTP compatibility adapter whose performance extension is documented separately.

A developer can clone the repository, verify the checked-in reference without
AWS credentials, or use the same contract and adapter interface for another
bounded classification service.

## Challenges

The largest challenge was separating a promising measurement from a claim that
could survive review. Early experiments helped choose the final rates but could
not approve the release. We therefore committed narrower capacity and Performix
contracts and ran fresh confirmation instances.

Profiling also required careful treatment. Performix function samples and Linux
perf cycle samples both show KleidiAI execution, but their percentages are not
directly interchangeable. The final adapter evaluates the frozen Performix
threshold in its native units and presents Linux perf as separate supporting
evidence.

Finally, the live application had to bind deployment behavior to the evidence.
The gateway now keeps the control active until a fresh audit passes, compares
the live source-model fingerprint and runtime shape with the release, and only
then changes the route.

## What We Learned

- Short tests suggested larger capacity gains, while 500-second windows exposed
  the reliable two-times lower bound.
- A favorable latency result is insufficient when a response cannot be tied to
  the measured source model and runtime; complete deployment identity matters.
- The Graviton virtual PMU supported Performix Code Hotspots but lacked enough
  counters for two heavier profiler recipes, so the release uses the supported
  evidence instead of inferring unavailable metrics.
- Connecting the audit to an actual service switch made the optimization easier
  to understand than a standalone benchmark page.

## Try It

Prerequisite: Python 3.12.

```bash
git clone https://github.com/QasimKhan5x/ArmProof.git
cd ArmProof
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/armproof ci examples/armproof-reference/armproof.json
python3.12 scripts/build_surgedesk_demo.py --verify
python3.12 scripts/serve_surgedesk.py --port 8765
```

Open <http://127.0.0.1:8765/surgedesk/>. The checked-in evidence path works
without AWS credentials. The complete live Graviton recording sequence is in
`submission/DEMO_SCRIPT.md`.

## Open Source, Data And Challenge Period

The project is MIT licensed. BANKING77 is used under CC BY 4.0 and credited in
`THIRD_PARTY_NOTICES.md`. Model weights are downloaded from their original
source and are not stored in this repository.

SurgeDesk and ArmProof were created and meaningfully developed from July 29
through August 5, 2026, during the challenge submission period. The public Git
history records the source changes, preregistrations, AWS experiments, evidence
and releases.
