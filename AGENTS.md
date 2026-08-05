# ArmProof Agent Instructions

## Mission

Build ArmProof, a fail-closed CI release gate that verifies whether an Arm AI
optimization preserves a declared quality contract, improves cloud-serving
performance, executes the required Arm acceleration path, and is reproducible.
SurgeDesk is the real banking-support reference application that demonstrates
the gate changing a live deployment from the control to the measured treatment.

ArmProof is not a generic benchmark dashboard, optimizer or formal attestation
system. SurgeDesk must remain a usable product workflow rather than a decorative
wrapper around the evidence report.

## Session Startup

1. Read `STATUS.md`.
2. Read the selected item in `ops/work-items.json`.
3. Load only that item's context pack or listed documents.
4. Inspect `git status` and work with existing changes.
5. Run the verified commands in `STATUS.md`.
6. Do not begin a dependent task while its gate is unresolved.

## Authority By Question

- Product intent: approved `docs/PRODUCT_SPEC.md`, then requirements.
- Technical truth: raw evidence and pinned source, then official docs.
- Repository state: source/tests/git, then `STATUS.md` and work items.
- Execution order: `tasks/plan.md`, `tasks/todo.md`, and accepted ADRs.
- Conversation, generated reports and README copy are non-authoritative.

When authorities conflict, record the conflict and update the correct source
of truth. Never silently choose convenient evidence.

## Non-Negotiable Rules

- Never fabricate, smooth, cherry-pick or relabel measurements.
- Keep whole-stack migration gains separate from KleidiAI-attributable gains.
- The KleidiAI causal comparison changes only its enable/disable control.
- A compiled or available backend is not proof that accelerated code executed.
- Missing, mismatched or unavailable required evidence fails closed.
- Every displayed claim resolves to raw samples, hashes and a reproduction
  command.
- Quality means compliance with the user-declared contract, not universal
  correctness or safety.
- Preserve failed and inconclusive runs.
- Never claim official Arm certification, universal optimality or a world
  first.
- Never provision paid cloud resources without explicit approval.
- Every cloud resource requires tags, TTL, spend cap and cleanup.
- Never commit secrets, gated models, private workloads or unlicensed data.

## Scope Boundaries

Supported reference path: Phi-4 Mini, PyTorch BF16, ONNX Runtime GenAI INT4,
KleidiAI, Linux Arm64 and AWS Graviton4.

Do not add vLLM, automatic parameter search, multi-cloud orchestration, hosted
SaaS, formal cryptography, training, fine-tuning or arbitrary model conversion
without an approved spec amendment. ADR-010 permits the existing
compatibility-only llama.cpp HTTP example; it carries no performance claim.

## Implementation Discipline

- Use Python 3.12 with typed, deterministic domain logic.
- Use structured subprocess argument arrays, never interpolated shell input.
- Version public schemas and machine-readable reason codes.
- Separate collection, normalization, policy decisions and presentation.
- Add focused tests before or with behavioral code.
- Keep each increment buildable and verify it before the next slice.

## Completion Protocol

1. Run the work item's verification commands.
2. Store raw outputs under `ops/evidence/<run-id>/` when applicable.
3. Append experiment metadata to `ops/experiments/registry.jsonl`.
4. Update the selected work item and `STATUS.md`.
5. Record consequential decisions in `docs/DECISIONS.md`.
6. Leave the tree in a verified state.

## Current Commands

```bash
make check
PYTHONPATH=src python3.12 -m armproof.cli ci \
  examples/armproof-reference/armproof.json
npm run test:logic
npm run test:ui
```
