# Requirements And Verification Questions

Requirement IDs are stable. Work items, tests, evidence, reports, and judging
claims must reference them.

## Product Invariants

### INV-01: Arm Evidence, Not Branding

Every optimization claim must identify the Arm CPU, supported ISA features,
selected KleidiAI path, and relevant fallback behavior.

**Stress questions**

- Would the exact same output be produced on x86? If yes, where is the
  Arm-specific contribution?
- Can a reviewer trace a headline speedup to an actual runtime/build/model
  difference rather than a label in the UI?
- Is KleidiAI execution observed or merely inferred from being compiled in?

### INV-02: End-To-End Artifact

The system must produce an evaluated candidate model, not only a trace,
recommendation, or dashboard.

**Stress questions**

- Where is the candidate GGUF checksum and exact recipe?
- Can a fresh machine reproduce the candidate and comparison?
- If candidate generation fails, does the system report failure clearly?

### INV-03: Quality Is A Hard Constraint

No speed or size win is accepted when the declared quality-loss budget fails.

**Stress questions**

- Was the quality metric selected before seeing results?
- Is the candidate compared to the correct F16/BF16 reference?
- Can changing the evaluation slice reverse the conclusion?

### INV-04: Existing Upstream Capabilities Are Baselines

Per-tensor quantization, importance matrices, and target-BPW optimization are
upstream capabilities, not KleidiScope inventions.

**Stress questions**

- Did the experiment include a size-matched `--target-bpw` candidate?
- Is improvement caused by Arm-aware policy or simply by upstream mixed
  precision?
- Does the project add useful dispatch explanation even when it cannot beat
  target-BPW performance?

### INV-05: Reports Derive From Raw Evidence

All visualizations and summaries must be reproducible projections of versioned
machine-readable evidence.

**Stress questions**

- Can every chart point be located in a raw file?
- Does changing a raw value and regenerating the report update the chart?
- Are missing samples shown rather than silently omitted?

## Functional Requirements

### FR-01 Environment Fingerprint

Record CPU identity/features, core count, memory, OS/kernel, compiler, build
flags, git revisions, dependency versions, thread/affinity settings, and active
power/performance controls where observable.

Verification: schema validation plus a fixture and one real Arm capture.

### FR-02 Structured Dispatch Trace

Capture a versioned event stream connecting workload phase, GGML operation,
tensor identity/type/shape, selected backend, selected kernel or kernel family,
eligibility decision, and fallback code.

Verification: golden synthetic fixture, real trace, source-line mapping, and
negative test with KleidiAI disabled.

### FR-03 Source-Grounded Explanation

Explain dispatch and fallback through rules extracted from the pinned upstream
source. Each explanation must carry a rule ID, source revision, and confidence.

Verification: rule tests covering eligible, ineligible, unknown, and version
mismatch cases.

### FR-04 Coverage Metrics

Report at least event-count, tensor-byte-weighted, and runtime-weighted
acceleration coverage. Keep observed duration separate from attributed kernel
time when attribution confidence differs.

Verification: hand-calculated fixture and reconciliation totals.

### FR-05 Ranked Opportunities

Rank fallbacks by measured significance and explain the expected tradeoff of
candidate tensor-format changes.

Verification: deterministic ranking fixture and explicit tie behavior.

### FR-06 Bounded Recipe Generation

Generate no more than a configured candidate count from an allowlisted set of
supported tensor types. Respect quality-sensitive tensor policies, size budget,
ISA/kernel eligibility, and unsupported-shape constraints.

Verification: property tests for budget, allowlist, determinism, and no-change
cases.

### FR-07 Upstream Quantizer Adapter

Render auditable `llama-quantize` commands using pinned, verified flags and
capture stdout, stderr, exit status, recipe, input/output hashes, and tool
revision.

Verification: command snapshot tests and a real candidate build from F16/BF16.

### FR-08 Evaluation Pipeline

Evaluate disk size, tensor distribution, RSS/peak RSS, quality, prompt
processing, generation, TTFT, latency, and throughput where applicable.

Verification: schema checks, repeatability checks, and intentionally failing
quality candidate.

### FR-09 Baseline Comparison

Compare at minimum:

1. F16/BF16 reference;
2. standard `Q4_K_M`;
3. a KleidiAI-friendly uniform or standard format such as `Q4_0`;
4. matched upstream `--target-bpw` optimization;
5. KleidiAI enabled versus disabled where technically valid; and
6. the KleidiScope candidate.

Verification: comparison refuses acceptance when a required baseline is absent.

### FR-10 Decision Gate

Accept, reject, or mark inconclusive using predeclared thresholds. Preserve all
candidates, including failures.

Verification: table-driven tests for pass, fail, missing, and noisy outcomes.

### FR-11 Evidence Bundle

Export manifest, trace, recipes, commands, logs, raw measurements, summaries,
checksums, licenses, and report inputs under a unique run ID.

Verification: bundle schema, checksum verification, and clean-room replay.

### FR-12 Interactive Report

Provide a clear operator-to-kernel X-ray, ranked fallbacks, candidate
comparisons, uncertainty, environment, and reproduction commands without
hiding failed runs.

Verification: browser tests at desktop/mobile sizes, accessibility checks,
fixture-driven screenshots, and raw-data links.

### FR-13 CI Regression Check

Allow a developer to fail CI when declared acceleration coverage or performance
regresses beyond a threshold, while distinguishing infrastructure noise from a
confirmed regression.

Verification: fixture-based passing/failing workflows and documented exit codes.

## Non-Functional Requirements

### NFR-01 Reproducibility

All evidence-bearing inputs and tools are pinned or checksummed. Randomness is
seeded. Commands are preserved verbatim.

### NFR-02 Statistical Rigor

Performance tests include warmup, repeated samples, ordering controls,
dispersion, and an inconclusive region. One-shot best numbers are forbidden.

### NFR-03 Low Perturbation

Tracing is opt-in, bounded, and measured. Disabled tracing must not impose a
material production penalty; enabled overhead must be reported.

### NFR-04 Determinism

Given the same normalized trace, policy, and source inventory, recipe output is
stable and order-independent.

### NFR-05 Failure Transparency

Unknown mappings, missing counters, timeouts, unsupported tensors, and partial
runs are explicit typed states, not empty strings or guessed values.

### NFR-06 Usability

A developer can reach a first report from documented prerequisites and a small
number of commands. Errors provide corrective action and preserve diagnostics.

### NFR-07 Portability

The orchestration and report layers run locally and on Linux Arm64. The
KleidiAI-specific analyzer fails clearly on unsupported architectures.

### NFR-08 Security

No model prompts, secrets, SSH keys, cloud credentials, or private evidence are
committed. Shell commands use structured argument lists where possible.

### NFR-09 Cost Safety

Cloud work requires explicit approval, TTL, tags, automatic termination,
budget alerts, and cleanup verification.

### NFR-10 Maintainability

Public schemas are versioned; upstream-specific logic is isolated; tests use
small fixtures; consequential decisions have ADR entries.

## Feasibility Acceptance Properties

- FP-01: Required dispatch evidence can be captured with a bounded patch.
- FP-02: Trace overhead is measurable and acceptable for profiling.
- FP-03: At least one fallback explanation is validated against source.
- FP-04: The generator creates a valid per-tensor candidate from F16/BF16.
- FP-05: Quality evaluation detects degradation.
- FP-06: Performance results are stable enough to distinguish a 10% change.
- FP-07: A candidate meets the primary gate or the project records a no-go.
- FP-08: The result is compared with matched target-BPW optimization.
- FP-09: Total AWS spend remains inside the approved ceiling.

## Final Agent Self-Interrogation

Before declaring the project complete, answer with evidence paths:

1. What exact operation changed, on what CPU, and which kernel handled it?
2. What would a generic x86 quantizer produce differently?
3. Which required baseline is hardest to beat, and was it included?
4. Did any rejected candidate outperform the winner on another metric?
5. How much does tracing perturb the result?
6. Can the full headline result be regenerated from a clean instance?
7. Which claim remains an inference rather than direct observation?
8. What happens on an unsupported model, tensor, ISA, or source revision?
9. Can another developer reuse the patch, schema, CLI, and CI check without
   adopting the demo model?
10. Which judging claim would collapse if one artifact were removed?

