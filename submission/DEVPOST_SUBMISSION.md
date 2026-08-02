# Copy-Ready Devpost Submission

## Project Metadata

**Project name:** SurgeDesk + ArmProof

**Tagline:** 3x the AI serving capacity on Graviton, with a release gate that proves every optimization claim.

**Track:** Cloud AI

**Repository:** https://github.com/QasimKhan5x/VerifyLane

**Try it:** https://qasimkhan5x.github.io/VerifyLane/surgedesk/

**Technical proof:** https://qasimkhan5x.github.io/VerifyLane/report/

**Release:** https://github.com/QasimKhan5x/VerifyLane/releases/tag/v0.2.0

**Video:** ADD THE PUBLIC YOUTUBE OR VIMEO URL AFTER RECORDING

**Built with:** AWS Graviton4, Arm KleidiAI, ONNX Runtime GenAI, Phi-4 Mini,
Python 3.12, Linux perf, GitHub Actions, BANKING77, JavaScript, HTML, CSS,
Playwright

**Hardest parts:** Measuring performance; improving model speed or latency;
improving inference server performance; understanding Arm-specific guidance;
finding compatible cloud hardware.

## Short Description

SurgeDesk is a human-confirmed banking-support triage application backed by a
measured Arm cloud optimization. On the same AWS Graviton4 instance, the same
Phi-4 Mini INT4 service sustained 3x higher confirmed tested mixed traffic with KleidiAI enabled while
remaining inside a 10-second p95 SLO. ArmProof is the reusable open-source
artifact behind the demo: a fail-closed CI gate that verifies quality,
capacity, executed Arm callchains, checksums and clean reproduction before an
optimized deployment can be released.

## Inspiration

Cloud AI optimization claims are usually presented as a benchmark screenshot.
That leaves maintainers with two problems: the benchmark is disconnected from
the user experience, and nothing prevents a later pull request from shipping
an unmeasured or regressed configuration.

We wanted to answer a more useful question: what does an Arm optimization buy
for a real service, and how can another developer verify the same kind of
claim in their own repository?

The result is two connected artifacts. SurgeDesk turns the performance gain
into an operational support workflow. ArmProof turns the experiment into a
repeatable release decision.

## What It Does

SurgeDesk routes BANKING77 customer messages into five operational support
queues. Phi-4 Mini proposes a fine-grained intent and procedure. A small,
dependency-free queue guard maps the request to an operational destination,
and a human confirms or corrects every route. The guard reaches 86.75% on a
disjoint 770-request holdout, 12.34 percentage points above direct LLM
intent-to-queue mapping.

The application then shows what changes under load. At an identical 0.267
requests/second, the KleidiAI-disabled service recorded 12.66 seconds p95 and
three SLO breaches across eight requests; the enabled service recorded 2.21
seconds p95 and zero breaches. Five confirmation runs at each passing boundary
confirmed 0.20 versus 0.60 requests/second tested mixed-traffic boundaries.

ArmProof evaluates the evidence behind that result. It verifies 282 files
across primary and clean-reproduction bundles, re-derives capacity and quality,
binds model/runtime/workload/environment identities, and only then evaluates a versioned contract
declares required quality, service-capacity, schema, attribution and
reproduction claims. Required failures or unknowns block the release. A
passing run emits:

- a machine-readable decision;
- an offline evidence report;
- the exact passing deployment manifest; and
- a GitHub Action result suitable for pull requests.

## What Was Optimized

The optimization has two deliberately separated comparisons.

First, Phi-4 Mini was migrated from PyTorch BF16 to an INT4 ONNX Runtime GenAI
deployment for CPU-only Graviton4 inference. Against BF16, the INT4 deployment
artifact was 35.92% smaller, peak proportional set size was 55.34% lower, and
time-weighted PSS was 59.66% lower.

Second, the Arm-specific effect was isolated inside the INT4 deployment. The
baseline and treatment used the same model bytes, ONNX Runtime GenAI build,
endpoint, 16 threads, one in-flight request, workload, instance and SLO. The
declared treatment control was KleidiAI enabled versus
`mlas.disable_kleidiai=1`. Across four batch/prompt shapes, KleidiAI improved
end-to-end execution by 1.72x to 2.59x. Linux perf callchains contained
`kai_*` frames only in the enabled treatment.

The service-level test used fixed-rate open-loop traffic, separate warmup,
passing/failing boundary discovery and five confirmation runs per treatment.
KleidiAI increased the highest confirmed tested capacity by 3.0x for short
traffic, 2.5x for long traffic and 3.0x for mixed traffic. A fresh
`c8g.4xlarge` reproduced all three tested ratios.

The queue guard improves application usefulness, but it is not presented as
an Arm speedup.

## How We Built It

1. We pinned the model, Arm64 runtime artifacts, service controls, workload
   and AWS Graviton4 environment.
2. We created matched ONNX Runtime GenAI overlays in which only the KleidiAI
   control differs.
3. We exposed every treatment through the same bounded HTTP inference
   contract and measured fixed-rate service capacity rather than relying only
   on a microbenchmark.
4. We evaluated both treatments on 770 frozen BANKING77 requests. Accuracy
   changed by -0.390 percentage points and macro F1 by -0.673 points, both
   inside the preregistered one-point tolerance; schema validity was 100%.
5. We captured positive and negative `kai_*` callchain evidence separately
   from the primary load run so profiler overhead could not contaminate it.
6. We reran the accepted protocol on a clean Graviton4 instance and compared
   metrics re-derived from the clean-instance raw evidence.
7. We built ArmProof around strict JSON schemas, immutable artifact identities,
   two SHA-256 ledgers, dependency-aware claims and pass/fail/unknown semantics.
   `armproof ci` rejects supplied normalized comparisons and derives its own.
8. We generated SurgeDesk through the same authoritative verification,
   derivation and policy path. Recorded
   mode never pretends edited text is live inference.

## Challenges

The hardest problem was not making inference run. It was proving why it ran
better.

An early memory experiment used loaded RSS as its gate and failed because
pre-inference RSS did not establish that model pages were resident. We kept
that failed experiment, preregistered a corrected follow-up and sampled
`/proc/self/smaps_rollup` throughout inference. The new experiment passed all
nine frozen gates. ArmProof preserves failed and unknown outcomes instead of
rewriting them into a success story.

Service capacity also required more than comparing requests per second. We
used the same p95 objective, fixed-rate arrivals, explicit passing and failing
boundaries, five confirmations per treatment, immutable request identities and
quality dependencies. Profiling ran separately, and an Arm claim could not
pass merely because KleidiAI was installed; executed `kai_*` frames were
required.

## Accomplishments

- 3.0x higher confirmed tested mixed and short traffic, and 2.5x long traffic, on the same
  Graviton4 instance.
- 1.72x to 2.59x direct KleidiAI execution speedup across four shapes.
- 35.92% smaller artifacts, 55.34% lower peak PSS and 59.66% lower
  time-weighted PSS after BF16-to-INT4 migration.
- A 770-request quality gate with 100% schema validity and less than one
  percentage point regression.
- Enabled-only `kai_*` runtime attribution and exact clean-instance
  reproduction.
- A tamper challenge that passes seven claims from 282 files, then proves one
  changed temporary ledger digest blocks release before policy evaluation.
- A zero-runtime-dependency Python CLI, reusable GitHub Action, strict public
  schemas, portable evidence ledger, deployment template and responsive
  offline report.
- Native Arm64, x86 and browser CI, including ten end-to-end UI workflows.

## What We Learned

Model conversion, Arm acceleration and service capacity are different claims
and need different controls. BF16-to-INT4 explains the size and memory change;
KleidiAI enabled versus disabled explains the Arm-specific execution change;
fixed-SLO traffic explains the operational capacity change.

We also learned that a typed result is insufficient if CI trusts it as input.
ArmProof therefore verifies raw evidence, derives its own comparison, binds
that comparison to the contract and only then emits the decision consumed by
the Action, report and SurgeDesk.

Finally, a benchmark becomes much easier to understand when it is attached to
a user outcome. In SurgeDesk, 3x capacity means a support queue remains inside
its response objective during a surge, not just that one isolated call ran
faster.

## Why It Matters To The Arm Community

The reference optimization is immediately reusable by developers evaluating
Phi-4 Mini, INT4 ONNX Runtime GenAI and KleidiAI on Arm cloud CPUs. The larger
contribution is the workflow:

- adapters for a common inference endpoint;
- fixed-SLO load and quality collectors;
- matched-treatment templates;
- public contract and decision schemas;
- primary and clean-reproduction SHA-256 evidence verification;
- raw-evidence derivation and contract identity binding;
- explicit Arm execution attribution;
- pass, fail and unknown fixtures;
- a GitHub Action and offline report; and
- an exact passing deployment manifest.

A maintainer can fork the repository, replace the model adapter and workload,
declare the claims that matter to their service, and make unproven Arm
optimization claims fail CI. No hosted service is required.

## Why It Should Win

This is not an AI application that merely happens to run on Arm. It combines a
real model migration, an isolated Arm-specific acceleration path, quality and
memory gates, service-level capacity testing, runtime attribution and clean
reproduction. It then converts those results into both a compelling cloud
application and a reusable developer workflow.

The headline is simple: the same Graviton4 instance served 3x higher confirmed
tested mixed AI traffic under the same p95 SLO. The implementation underneath that sentence is inspectable,
fail-closed and available for another Arm developer to adopt.

## What's Next

- Add first-class adapters and examples for llama.cpp, vLLM and additional
  ONNX Runtime workloads.
- Add an optional Arm Performix importer while keeping profiler runs separate
  from primary measurements.
- Validate the same contract on Google Axion and Microsoft Cobalt.
- Publish reusable contract templates for generation, vision and speech
  workloads.
- Add signed evidence bundles and commit-status annotations for larger teams.

## Setup And Validation

```bash
git clone https://github.com/QasimKhan5x/VerifyLane.git
cd VerifyLane
python3.12 -m pip install -e .
make check
armproof ci examples/armproof-reference/armproof.json
python3.12 scripts/demo_release_gate.py
python3.12 scripts/serve_surgedesk.py --port 8765
```

Open `http://127.0.0.1:8765/surgedesk/`. The accepted report is also checked
in under `report/`, so judging does not depend on AWS availability.

Verify the relocated raw evidence independently:

```bash
armproof evidence-verify \
  --checksums ops/evidence/EXP-2026-004/accepted/evidence/SHA256SUMS \
  --root ops/evidence/EXP-2026-004/accepted/evidence
```

The full Graviton service recipe, runtime lock, matched treatment generation,
systemd unit and passing deployment are under `examples/phi4-graviton/` and
`deploy/`.

## Open Source And Data

Project source is MIT licensed. BANKING77 is used under CC BY 4.0 and is
attributed in `THIRD_PARTY_NOTICES.md`. Large model weights are not
redistributed by this repository.
