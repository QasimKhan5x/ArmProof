# Architecture And Product Decisions

## ADR-001: KleidiScope GGUF Optimizer

- Status: superseded on 2026-07-31.
- Previous decision: build a `llama.cpp`/GGUF tracing and mixed-quantization
  optimizer.
- Reason superseded: feasibility work found no runtime-significant fallback
  surface or credible candidate advantage for the planned optimization thesis.

Historical documents must not be treated as active requirements.

## ADR-002: Use The Validated Phi-4/KleidiAI Mechanism

- Status: accepted.
- Decision: productize the established Phi-4 Mini INT4 ONNX Runtime GenAI and
  KleidiAI evidence rather than search for another optimization.
- Reason: direct speed, PSS, size, quality and attribution findings are already
  measured on Graviton4.

## ADR-003: ArmProof Is A PR Release Gate

- Status: amended by ADR-011.
- Decision: the primary workflow is a CI merge/deployment decision for an Arm
  AI optimization PR.
- Reason: this is recurring developer work and avoids a staged application
  narrative. A support workload is only a reference fixture.

## ADR-004: Fail-Closed Claim Ledger

- Status: accepted.
- Decision: every claim binds to identities, raw evidence, comparison,
  threshold and reproduction command. Required unknown evidence fails.
- Reason: a report around one hand-built experiment is not a reusable product.

## ADR-005: Separate Causal Scopes

- Status: accepted.
- Decision: BF16-to-INT4 describes the whole deployment transformation;
  identical INT4 KleidiAI off/on isolates Arm acceleration; fixed-SLO load
  testing describes cloud capacity.
- Reason: combining them would overstate Arm attribution.

## ADR-006: One Excellent Runtime Adapter

- Status: accepted.
- Decision: ship the ONNX Runtime GenAI/KleidiAI reference path. Defer vLLM,
  llama.cpp and additional clouds.
- Reason: shallow integrations weaken trust and completion quality.

## ADR-007: Capacity Gate Before UI Critical Path

- Status: accepted.
- Decision: implement the reusable service/load harness and run fixed-SLO
  validation before investing heavily in report polish.
- Reason: the Cloud AI and grand-prize story depends on deployable capacity.

## ADR-008: MIT Project And CC-BY-4.0 Workload

- Status: accepted.
- Decision: preserve the owner-selected MIT license and preserve BANKING77 as
  separately attributed CC-BY-4.0 material.
- Reason: permissive reuse is central to the community artifact, while the
upstream dataset's attribution terms must remain explicit.

## ADR-009: Publish The Sustained Lower Bound, Not The Short-Window Headline

- Status: superseded by ADR-012 after serving as discovery evidence.
- Decision: the judge-facing capacity claim is at least 2.0x sustained mixed
  traffic. Display all four tested boundaries and twenty outcomes; derive the
  lower bound from the optimized passing boundary and baseline failing boundary.
- Reason: EXP-2026-009 confirmed disabled 0.24 r/s and enabled 0.56 r/s in all
  five 500-second windows and baseline failure at 0.28 r/s, but enabled 0.60
  r/s passed one window. The lower bound is fully supported; an exact bracket
  is not. The unstable probe remains visible in the trial matrix without being
  turned into a separate headline.

## ADR-010: Permit One Non-Claiming llama.cpp Adoption Example

- Status: accepted on 2026-08-04.
- Decision: add one tested llama.cpp compatibility example through the generic
  HTTP SLO interface. It may prove protocol compatibility and onboarding, but
  it may not publish performance, quality or Arm-acceleration results without
  real checksum-bound evidence.
- Reason: the submission needs to demonstrate that ArmProof is not coupled to
  Phi-4 or ONNX Runtime while preserving the single measured reference and its
  causal boundaries.

## ADR-011: Connect The Release Gate To A Real Product Action

- Status: accepted on 2026-08-04.
- Decision: SurgeDesk is the primary demo surface. A real support request uses
  the control lane, the evidence audit authorizes a deployment change, and the
  next real request records the optimized lane and authorizing audit.
- Reason: the optimization becomes understandable when it changes visible
  product behavior. ArmProof remains the reusable community artifact behind the
  action rather than a standalone dashboard.

## ADR-012: Require Fresh One-Sided Capacity And Performix Confirmation

- Status: accepted on 2026-08-04.
- Decision: the public release consumes only the two rates frozen in
  EXP-2026-014 and the Code Hotspots thresholds frozen in EXP-2026-013. Earlier
  capacity and profiler runs remain discovery history.
- Reason: the final evidence must be independent of rate selection and must use
  a profiler recipe supported by the Graviton virtual PMU. Release-time config
  cannot replace either preregistration's rates or thresholds.

## ADR-013: Reject Capacity Evidence Missing Response-Level Source Identity

- Status: accepted on 2026-08-04.
- Decision: EXP-2026-012 remains rejected even though its capacity outcomes
  matched the frozen rates. EXP-2026-014 reruns the same rates, workload, model,
  runtime and SLO after adding the required source-artifact hash to every
  successful response.
- Reason: endpoint labels and matching model identities do not satisfy the
  preregistered source-provenance rule. The public result must pass the same
  analyzer shipped to judges.

## Pending Decisions

- Whether to promote the compatibility-only llama.cpp bridge into a measured
  adapter after the hackathon.
