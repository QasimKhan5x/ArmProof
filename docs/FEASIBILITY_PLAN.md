# Feasibility Plan

The feasibility phase exists to kill weak assumptions before building the full
CLI and report. It is not a miniature final product.

## Questions In Risk Order

1. Can we observe enough dispatch detail to distinguish real KleidiAI kernel
   usage from backend availability?
2. Can fallback reasons be mapped to pinned source rules accurately?
3. Can tensor-format changes alter useful Arm execution behavior rather than
   merely change file size?
4. Can quality be kept inside a declared budget?
5. Can a hardware-aware candidate beat or complement upstream target-BPW?
6. Are results stable enough for a judgeable claim?

## Fixed Environment

- Primary machine: AWS `c8g.2xlarge`, Graviton4, 8 cores, 16 GiB.
- Fallback only if memory is measured insufficient: `c8g.4xlarge`, 16 cores,
  32 GiB.
- Region: `us-east-1`, subject to availability and final price check.
- OS: Ubuntu 24.04 Arm64.
- Runtime: one pinned `llama.cpp` commit with its pinned/submodule KleidiAI.
- Compiler/build: recorded exactly; CPU-only; higher-priority GPU backends off.
- Model: ungated 3B-class instruct model with license permitting artifacts.
- Source model: F16/BF16, never a requantized low-bit source for headline proof.
- Workloads: fixed prompt-processing/decode cases plus one server workload.
- Quality: fixed calibration and held-out evaluation slices.

## Local-First Preparation

Complete without paid AWS:

- source reconnaissance and proposed trace schema;
- minimal patch design and compile checks on available Arm64/GitHub Actions;
- parser, rule engine, recipe generator, and report fixtures;
- workload and evaluation download scripts;
- full experiment orchestration in dry-run mode;
- AWS launch/TTL/cleanup scripts;
- manifest and evidence schemas;
- unit, property, and contract tests.

Do not start paid compute until one command can provision or connect, build,
run the bounded experiment, retrieve evidence, and terminate.

## Experiment 0: Upstream Reconnaissance

### Deliverables

- Pinned source revisions.
- Dispatch path map from GGML operation to KleidiAI eligibility and kernel.
- Inventory of observable versus inferred fields.
- Minimal patch proposal with expected overhead and upstream boundary.
- Verified quantizer flag inventory, including `--tensor-type`, imatrix, and
  target-BPW behavior.

### Gate

Proceed only if operator/tensor/backend/kernel evidence can be captured without
forking broad runtime behavior. If exact kernel identity is impossible, narrow
the product claim before implementation.

## Experiment 1: Trace Truthfulness

Run one tiny compatible GGUF with KleidiAI enabled and disabled.

### Required Evidence

- Environment manifest.
- Structured trace and raw runtime log.
- At least one verified accelerated event.
- At least one deliberate ineligible/fallback fixture or event.
- Source references for both paths.
- Trace reconciliation totals.
- Enabled-versus-disabled trace difference.

### Gate

- No false assertion of acceleration in the disabled run.
- Unknowns remain unknown.
- Trace overhead can be quantified.

## Experiment 2: Baseline Matrix

Build or obtain from the same source:

- F16/BF16 reference;
- Q8_0;
- Q4_K_M;
- Q4_0 or another explicitly KleidiAI-relevant format;
- target-BPW candidate matched to the intended KleidiScope size;
- KleidiAI enabled/disabled builds where meaningful.

Measure size, RSS, quality, PP, TG, and coverage before recipe generation. This
establishes whether the optimization surface exists.

## Experiment 3: Bounded Candidate Generation

Generate no more than three first-round recipes:

1. **Coverage repair:** prioritize expensive fallbacks with supported formats.
2. **Quality guard:** restore precision to the most sensitive tensors.
3. **Pareto compromise:** combine the best validated changes under target BPW.

Every recipe must explain each override through trace evidence, kernel
eligibility, expected size change, and quality sensitivity. No unconstrained
grid search is allowed.

## Experiment 4: Quality And Performance

Evaluate all required baselines and candidates using the protocol in
`BENCHMARK_PROTOCOL.md`.

### Primary Gate

At least one candidate must show either:

- >=10% improvement in the predeclared primary speed metric while satisfying
  the quality budget; or
- >=10% disk/RSS reduction, <=3% speed regression, and quality inside budget.

It must also provide one of:

- a measured advantage over size-matched target-BPW; or
- materially higher explained/accelerated coverage with a credible deployment
  benefit not captured by target-BPW.

### Secondary Evidence

- tracing overhead;
- repeated-run dispersion;
- server TTFT and p95 at fixed concurrency;
- recipe stability across two workload slices;
- cost per successful experiment.

## Experiment 5: Reproduction

Destroy the original instance. On a clean Graviton4 instance, use only the
repository, public model/data references, and evidence manifest to reproduce
the headline comparison.

### Gate

Headline direction and acceptance decision reproduce. Exact timings may vary
within the protocol's declared tolerance.

## Stop Conditions

Stop or redesign when:

- dispatch evidence cannot support the advertised granularity;
- tracing changes performance too much to be useful and cannot be sampled;
- all candidate changes reduce quality outside budget;
- target-BPW matches or dominates candidates and coverage insight has no
  actionable value;
- repeated-run noise prevents distinguishing the target effect;
- projected AWS spend exceeds the approved ceiling;
- the contribution reduces to a generic quantization search.

## Feasibility Output

Produce one of three explicit decisions:

- **GO:** central mechanism and primary gate pass.
- **PIVOT:** observability is useful but optimization claim must narrow.
- **STOP:** no defensible Arm-specific contribution was demonstrated.

