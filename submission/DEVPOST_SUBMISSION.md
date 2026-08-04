# Copy-Ready Devpost Submission

## Project Metadata

**Project name:** SurgeDesk + ArmProof

**Tagline:** At least 2x sustainable AI capacity on Graviton, with a release gate honest enough to reject its own prettier number.

**Track:** Cloud AI

**Repository:** https://github.com/QasimKhan5x/ArmProof

**Try it:** https://qasimkhan5x.github.io/ArmProof/surgedesk/

**Technical proof:** https://qasimkhan5x.github.io/ArmProof/report/

**Release:** https://github.com/QasimKhan5x/ArmProof/releases/tag/v0.5.1

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
Phi-4 Mini INT4 service sustained at least 2x more mixed traffic with KleidiAI
enabled while remaining inside a 10-second p95 SLO. ArmProof is the reusable open-source
artifact behind the demo: a fail-closed CI gate that verifies quality,
capacity, executed Arm callchains and checksums before an
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

The application first shows a supporting equal-load slice from `EXP-2026-004`.
At an identical 0.267
requests/second, the KleidiAI-disabled service recorded 12.66 seconds p95 and
three SLO breaches across eight requests; the enabled service recorded 2.21
seconds p95 and zero breaches. The decisive sustained audit then ran five
500-second confirmations at every boundary. Baseline `0.24 r/s` and optimized
`0.56 r/s` passed all five; baseline `0.28 r/s` failed all five. This proves an
at-least-2.0x sustainable-capacity improvement and a 2.33x tested pass-point ratio.
ArmProof re-derives all 4,200 raw request outcomes across the 20 long windows.

ArmProof evaluates the sustained result from its SHA-256 locked 69-file archive.
It re-derives capacity and quality, binds model/runtime/workload/environment
identities, and only then evaluates nine required quality, service-capacity,
schema, attribution and profiler-integrity claims. Supporting EXP004/EXP005
bundles remain separately identified. Required failures or unknowns block the
release. The reusable reference workflow emits:

- a machine-readable decision;
- an offline evidence report;
- a pinned conservative deployment manifest; and
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
end-to-end execution by 1.72x to 2.59x. Linux perf attributed 68.53% of sampled
cycles to the KleidiAI matmul callchain in the enabled treatment and none in
the disabled control.

The decisive service-level test used fixed-rate open-loop traffic, process
isolation and five 500-second confirmations at four frozen pass/fail points.
The original exact 2.5x bracket gate was rejected because optimized `0.60 r/s`
passed one window by 72 ms. ArmProof emitted no exact bracket. The unchanged
rows still prove at least 2.0x sustainable capacity: optimized `0.56 r/s`
passed all five while baseline `0.28 r/s` failed all five. The failed gate is
preserved and visible in the product rather than rewritten as a success.

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
6. We reproduced the earlier short-window grid on a clean Graviton4 instance;
   it remains supporting history and is not presented as reproduction of the
   later 500-second sustained audit.
7. We built ArmProof around strict JSON schemas, immutable artifact identities,
   two SHA-256 ledgers, dependency-aware claims and pass/fail/unknown semantics.
   `armproof ci` rejects supplied normalized comparisons and derives its own.
8. We generated SurgeDesk through ArmProof's shared verify-derive-bind-decide
   architecture with a dedicated sustained-evidence adapter. Recorded
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

- At least 2.0x higher sustainable mixed traffic on the same Graviton4
  instance, with a 2.33x tested pass-point ratio over 4,200 requests in twenty
  500-second windows.
- 1.72x to 2.59x direct KleidiAI execution speedup across four shapes.
- 35.92% smaller artifacts, 55.34% lower peak PSS and 59.66% lower
  time-weighted PSS after BF16-to-INT4 migration.
- A 770-request quality gate with 100% schema validity and less than one
  percentage point regression.
- 68.53% sampled-cycle attribution to the enabled KleidiAI matmul callchain,
  absent from the control, with zero lost profiler samples.
- A tamper challenge that passes eight release claims from 282 files, plus a
  SHA-256 locked 69-file sustained audit that blocks the original exact bracket;
  one changed temporary ledger digest also blocks before policy evaluation.
- A zero-runtime-dependency Python CLI, reusable GitHub Action, strict public
  schemas, portable evidence ledger, deployment template and responsive
  offline report.
- Native Arm64, x86 and browser CI, including eleven end-to-end UI workflows.
- A fail-closed `armproof init` scaffold and a real llama.cpp/Qwen2.5 HTTP
  compatibility smoke, kept separate from measured optimization claims.

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
a user outcome. In SurgeDesk, at least 2x capacity means a support queue remains inside
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
- portable SHA-256 evidence verification, plus a sustained-archive adapter;
- raw-evidence derivation and contract identity binding;
- explicit Arm execution attribution;
- pass, fail and unknown fixtures;
- a GitHub Action and offline report;
- a pinned conservative deployment manifest;
- a one-command fail-closed adoption scaffold; and
- a tested llama.cpp bridge with no fabricated performance claim.

A maintainer can fork the repository, replace the model adapter and workload,
declare the claims that matter to their service, and make unproven Arm
optimization claims fail CI. No hosted service is required.

## Why It Should Win

This is not an AI application that merely happens to run on Arm. It combines a
real model migration, an isolated Arm-specific acceleration path, quality and
memory gates, service-level capacity testing, runtime attribution and
an honestly scoped supporting reproduction. It then converts those results into both a
compelling cloud application and a reusable developer workflow.

The headline is simple: the same Graviton4 instance sustained at least 2x more
mixed AI traffic under the same p95 SLO. The more important technical signal is
that ArmProof rejected an initially stronger 2.5x claim when one long window
contradicted it, then exposed only the lower bound supported by every run. The
implementation is inspectable and available for another Arm developer to adopt.

## What's Next

- Promote the llama.cpp compatibility bridge to a measured adapter, then add
  vLLM and additional ONNX Runtime workloads.
- Add an optional Arm Performix importer while keeping profiler runs separate
  from primary measurements.
- Validate the same contract on Google Axion and Microsoft Cobalt.
- Publish reusable contract templates for generation, vision and speech
  workloads.
- Add commit-status annotations and organizational policy templates for larger teams.

## Setup And Validation

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
