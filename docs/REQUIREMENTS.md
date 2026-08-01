# ArmProof Requirements And Stress Questions

Requirement IDs are stable. Tests, work items, evidence and submission claims
must reference them.

## Invariants

### INV-01: Arm Causality

An Arm-specific claim requires a matched treatment/control and observed Arm
execution evidence.

- Is the model, runtime, workload, thread configuration and machine identical?
- Is only the KleidiAI control different?
- Does enabled evidence contain executed `kai_*` callchains while disabled
  evidence does not?

### INV-02: Honest Causal Scope

Whole-stack migration, quantization/runtime transformation and KleidiAI
acceleration must not be conflated.

- Which exact comparison supports each number?
- Would the report still be truthful if the KleidiAI speedup were zero?

### INV-03: Quality Is A Contract

Performance cannot pass when the declared task-quality tolerance fails.

- Was the metric and tolerance frozen before the accepted run?
- Are malformed and missing outputs counted as failures?
- Does "pass" mean only this workload rather than universal safety?

### INV-04: Fail Closed

Missing, mismatched, stale or unavailable required evidence prevents approval.

- What happens when an artifact hash changes?
- Can a report display a claim whose raw samples were removed?
- Is unknown distinct from pass, fail and not-applicable?

### INV-05: Reproducible Deployment

The accepted configuration must be the configuration that can be deployed and
reproduced.

- Does the generated manifest pin the measured artifacts and flags?
- Can a clean machine reproduce the decision without manual repair?

## Functional Requirements

- **FR-01 Contract validation:** reject invalid or ambiguous contracts before
  execution.
- **FR-02 Identity capture:** hash artifacts, workloads, commands, runtime and
  relevant environment facts.
- **FR-03 Treatment execution:** run declared treatments with bounded lifecycle
  and readiness behavior.
- **FR-04 Workload replay:** support frozen short, long and mixed traffic.
- **FR-05 Resource measurement:** collect latency, throughput, RSS and PSS with
  raw timestamped samples.
- **FR-06 Quality evaluation:** apply a pluggable task metric and count malformed
  output.
- **FR-07 Arm attribution:** capture and normalize positive/negative `kai_*`
  execution evidence.
- **FR-08 Claim ledger:** bind each claim to its comparison, evidence and
  decision rule.
- **FR-09 Verification:** independently validate a completed evidence bundle.
- **FR-10 Reporting:** render an offline interactive report from verified data.
- **FR-11 CI decision:** emit stable exit codes and a GitHub Check summary.
- **FR-12 Deployment output:** emit the exact accepted service configuration.
- **FR-13 Reproduction:** provide one documented clean-run command.
- **FR-14 Application workflow:** route recorded BANKING77 requests through an
  explicit human confirmation or correction step.
- **FR-15 Surge replay:** animate raw accepted baseline and optimized request
  samples and converge on their measured p95, breaches and capacity boundary.
- **FR-16 Evidence-derived demo:** generate all product-demo metrics and cases
  from accepted files; checked output drift must fail CI.
- **FR-17 Operational quality:** evaluate the five-destination product task on a
  frozen 770-case holdout disjoint from queue-guard training and require at
  least 85% accuracy.
- **FR-18 Live demonstration:** optionally route bounded text through the
  trusted `/infer` contract; remain explicitly recorded-only when unavailable.

## Non-Functional Requirements

- **NFR-01 Determinism:** fixed inputs and identities produce the same policy
  decision.
- **NFR-02 Overhead:** non-profiler measurement overhead remains below 5%.
- **NFR-03 Security:** no shell interpolation of workload data; no secrets in
  evidence or reports.
- **NFR-04 Portability:** reports work offline; core policy tests run without
  Arm hardware.
- **NFR-05 Explainability:** every failure has a stable reason code and human
  explanation.
- **NFR-06 Accessibility:** the report is keyboard-usable, readable and
  responsive.
- **NFR-07 Bounded cost:** cloud runs enforce approval, TTL, tags and spend cap.
- **NFR-08 Demo integrity:** offline replay is labeled as recorded evidence;
  edited text cannot masquerade as live model output.
- **NFR-09 Gateway safety:** live requests are size-bounded, timeout-bounded and
  forwarded only to the operator-configured endpoint.

## Product Properties

- **P-01 Existing evidence imports without reinterpretation.**
- **P-02 Unfavorable samples remain present.**
- **P-03 Swapping one artifact invalidates dependent claims.**
- **P-04 Disabling KleidiAI invalidates the Arm execution claim.**
- **P-05 Report, CLI and GitHub Check produce the same decision.**
- **P-06 The reference recipe is replaceable through documented adapter
  boundaries, not hardcoded presentation logic.**
- **P-07 A failed contract remains useful and understandable.**

## Final Agent Stress Test

Before marking the product complete, answer with evidence:

1. What exact comparison proves the Arm-specific speedup?
2. Which gains come from the whole migration rather than KleidiAI?
3. Can a compiled-but-unused KleidiAI path pass?
4. What happens when raw samples, hashes or profiler evidence are missing?
5. Is the deployment manifest identical to the measured passing treatment?
6. Can a fresh developer run it from one YAML file and one command?
7. Does the report remain honest when a metric is unfavorable or unavailable?
8. What disappears on x86, and is that boundary visible?
9. Can changing a visible demo number without changing raw evidence pass CI?
10. Are 86.75% queue accuracy and 46.49% intent accuracy clearly distinguished?
11. Can the live control appear when no endpoint is configured or silently
    fall back to recorded output?
