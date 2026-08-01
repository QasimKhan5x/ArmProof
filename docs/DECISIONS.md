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

- Status: accepted.
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

## Pending Decisions

- Public repository name and remote.
- Whether to add a second adapter after the hackathon.
