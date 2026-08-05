# Product Specification: ArmProof

Status: **APPROVED**

Version: **1.3.0**

Approved by: Qasim Khan

Approved date: 2026-07-31

## Objective

Build a reusable CI release gate for Arm AI optimization pull requests. Given
a baseline, one or more treatments, a representative workload and a declared
quality/performance contract, ArmProof must issue a reproducible merge decision
and reject unsupported claims.

Success means a maintainer can answer, before merge:

1. Did the deployment preserve the declared task quality?
2. Did it improve fixed-instance cloud-serving capacity or latency?
3. Did the required Arm acceleration path execute?
4. Which gains are attributable to that Arm path?
5. Can the decision and passing deployment be reproduced from pinned evidence?

## Primary User And Job

An inference maintainer or ML platform engineer reviewing an Arm64
optimization PR needs trustworthy evidence to accept or reject the change.

The submission showcase adds a support-operations user. The operator needs an
assistive route suggestion and a responsive queue during traffic spikes, while
the platform engineer needs proof that the deployed Arm treatment caused the
capacity gain without violating the quality contract.

## Reference Application

SurgeDesk must present one continuous workflow: human-confirm a real banking
request on the control service, re-derive the EXP-2026-014 release from raw
capacity and quality rows, inspect native Arm attribution, identity-match and
activate the measured treatment, route a second real request through it, and
generate a reusable ArmProof starter. Edited free-form text must never be
represented as recorded model inference.

The routing path is two-stage: Phi-4 Mini proposes a fine-grained intent and a
dependency-free queue guard assigns the operational queue. The guard trains on
2,310 examples disjoint from the frozen 770-case evaluation and must achieve at
least 85% queue accuracy. A configured gateway may replace recorded Phi-4
output with the same live `/infer` contract; it may not fake availability.

## Reference Scope

| Layer | Approved reference |
|---|---|
| Cloud target | AWS Graviton4 `c8g.4xlarge`, CPU-only |
| Model | Phi-4 Mini |
| Baseline | PyTorch BF16 |
| Optimized runtime | ONNX Runtime GenAI INT4 |
| Arm acceleration | KleidiAI enabled/disabled matched control |
| Orchestration | Python 3.12 |
| Contracts | JSON input and versioned JSON Schema evidence |
| Report | Static interactive web report |
| CI | Portable GitHub Action consuming trusted Graviton evidence |

The measured reference remains one excellent adapter. A compact llama.cpp
compatibility example may demonstrate the runtime-neutral HTTP adoption path,
but it must not publish an unmeasured optimization or capacity claim.

## Required Workflow

1. Validate the versioned ArmProof config before evaluating evidence.
2. Fingerprint model, runtime, workload, environment and commands.
3. Run baseline and treatments under declared controls.
4. Collect output, quality, latency, throughput, PSS and matched Arm Performix
   profiles for the control and optimized treatments.
5. Normalize raw measurements without deleting unfavorable samples.
6. Evaluate claims using explicit causal scopes.
7. Fail closed for missing, mismatched or unavailable required evidence.
8. Emit a machine-readable decision, report and reproduction bundle.
9. Post the decision as a GitHub Check.
10. Make the passing configuration deployable without manual reconstruction.

## Public Interface Contract

```bash
armproof capacity --endpoint URL --workload WORKLOAD [policy options]
armproof quality --endpoint URL --dataset DATASET [policy options]
armproof verify --contract CONTRACT --comparison COMPARISON
armproof report --decision DECISION --summary SUMMARY --comparison COMPARISON \
  --verification VERIFICATION --output REPORT
armproof ci armproof.json
armproof init --endpoint URL --output DIRECTORY
```

`armproof ci` is the one-command release gate. Collection remains explicit so
benchmark execution can stay on a trusted Arm runner while policy and report
generation run on any GitHub runner.

## Architecture Constraints

- Collection, normalization, policy and presentation remain separate modules.
- Claims reference immutable evidence IDs; reports never calculate hidden
  replacement metrics.
- The KleidiAI treatment differs from its control only by the documented
  enable/disable mechanism.
- Whole-stack and KleidiAI-specific gains are displayed separately.
- Reports work offline from the evidence bundle.
- Subprocess input uses structured arguments and bounded timeouts.

## Testing Strategy

- Unit tests: schemas, normalization, statistics, policy and reason codes.
- Contract tests: valid and invalid evidence/contract fixtures.
- Integration tests: process lifecycle, PSS sampling, live matched requests and
  profiler parsing.
- Negative tests: missing evidence, swapped artifacts, disabled KleidiAI and
  revision mismatch.
- End-to-end tests: fixture to report, PR check and generated deployment.
- Browser tests: decision, failed-state, provenance and responsive layout.
- Performance claims: only under `BENCHMARK_PROTOCOL.md`.

## Success Criteria

### Product Core

- One command evaluates the reference contract from a clean environment.
- Every displayed claim resolves to raw, hashed evidence.
- Removing or swapping required evidence makes the decision fail.
- Disabling KleidiAI removes `kai_*` attribution and fails the Arm contract.
- Removing either matched Performix export, changing its workload identity, or
  contradicting the accepted Linux profiler attribution fails the reference
  Arm contract.
- The report and GitHub Check agree with the machine-readable decision.
- A passing report is impossible without a verification receipt cryptographically
  bound to its decision, comparison and summary.

### Cloud Gate

- The canonical release result is at least 2.0x sustainable mixed-traffic
  capacity at the same 10-second p95 SLO, established from five 500-second
  confirmations at each stable pass/fail boundary.
- Quality loss is no more than one percentage point under the frozen task
  metric, with at least 99% schema-valid outputs.
- Matched Performix and Linux `perf` evidence independently observe the enabled
  Arm path, while the control remains negative.
- Policy and report generation stay out of the serving measurement path;
  profiler runs are separate and never used as capacity samples.

### Community And Submission

- Public GitHub Action, schemas, reference recipe, report and tutorial.
- Fresh-user quickstart requires one contract file and one command.
- Every Devpost number maps to a claim and raw evidence.
- No submission copy implies official Arm certification.
- A judge can move from customer request to service surge to causal Arm proof
  in under three minutes without terminal narration.
- A fresh developer can scaffold the runtime-neutral HTTP adoption path with
  one command and receives explicit fail-closed next steps rather than
  synthetic passing evidence.
- The quality boundary and human-confirmation requirement remain visible.
- Live product requests and the previously collected confirmation evidence
  remain visually and verbally distinct.

## Boundaries

Always preserve raw evidence, pin identities, test negative paths and update
the spec before scope changes.

Ask before adding dependencies, changing public schemas or thresholds,
provisioning paid infrastructure, selecting a license, or adding a runtime.

Never commit secrets or unlicensed data, hide failed runs, call backend
availability execution evidence, or attribute whole-stack gains to KleidiAI.

## Deferred Decisions

- Public repository name and remote configuration.
- Whether additional measured runtime adapters are justified after submission.
