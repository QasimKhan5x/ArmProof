# ArmProof Implementation Plan

Status: **APPROVED FOR IMPLEMENTATION**

## Dependency Graph

```mermaid
graph TD
  CTX[CTX-001] --> EVID[EVID-001]
  CTX --> BOOT[BOOT-001]
  CTX --> SCHEMA[SCHEMA-001]
  CTX --> DATA[DATA-001]
  CTX --> AWS[AWS-001]
  EVID --> CORE[CORE-001]
  BOOT --> CORE
  SCHEMA --> CORE
  BOOT --> QUALITY[QUALITY-001]
  SCHEMA --> QUALITY
  DATA --> QUALITY
  CORE --> FIXTURE[FIXTURE-001]
  BOOT --> SERVICE[SERVICE-001]
  SCHEMA --> SERVICE
  CORE --> LOAD[LOAD-001]
  SERVICE --> LOAD
  DATA --> LOAD
  EVID --> CAP[CAP-001]
  QUALITY --> CAP
  AWS --> CAP
  LOAD --> CAP
  FIXTURE --> REPORT[REPORT-001]
  CAP --> REPORT
  CORE --> ACTION[ACTION-001]
  CAP --> ACTION
  SERVICE --> DEPLOY[DEPLOY-001]
  CAP --> DEPLOY
  REPORT --> REPRO[REPRO-001]
  ACTION --> REPRO
  DEPLOY --> REPRO
  REPRO --> DEMO[DEMOAPP-001]
  CAP --> PERF[PERF-001]
  AWS --> PERF
  PERF --> SHIP
  DEMO --> SHIP[SHIP-001]
```

Exact dependencies and status live in `ops/work-items.json`.

## Phase 0: Foundation

- Import and hash existing evidence.
- Establish verified Python build/test/lint commands.
- Freeze contract, evidence and claim schemas.
- Select and license the larger reference workload.
- Update the AWS lifecycle for ArmProof.

Checkpoint: existing claims validate from imported evidence without AWS.

## Phase 1: Fail-Closed Vertical Slice

- Implement schema loading and identity validation.
- Implement claim dependencies, causal scopes and stable reason codes.
- Generate one decision and report from fixture/imported evidence.
- Add tamper, missing-evidence and disabled-KleidiAI tests.

Checkpoint: CLI, decision artifact and fixture report agree.

## Phase 2: Real Service Harness

- Implement common HTTP treatment adapters.
- Implement deterministic workload replay and quality evaluation.
- Collect request metrics, RSS/PSS and separate Arm attribution.
- Measure normal collection overhead.

Checkpoint: lifecycle and negative paths pass on a free/local environment;
Arm-only attribution smoke runs on available Arm64 hardware.

## Phase 3: Fixed-SLO Capacity Gate

- Preregister the exact experiment.
- Run one bounded `c8g.4xlarge` session.
- Evaluate without changing thresholds.

Checkpoint: `CAPACITY_VALIDATION.md` returns pass before polished product work
becomes the critical path. Failure returns to the owner; no weaker pivot is
automatic.

## Phase 4: Community Product

Parallel lanes after schemas and accepted capacity evidence:

- interactive report and browser tests;
- GitHub Action and PR check;
- exact deployment manifest;
- adapter/workload authoring docs.

Checkpoint: one YAML and one command drive a useful passing or failing PR
decision.

## Phase 5: Reproduction And Submission

- Clean-room Graviton replay.
- Matched Arm Performix causal characterization and native export validation.
- Evidence-backed SurgeDesk application workflow.
- Security, licensing, accessibility and secret checks.
- Demo, offline fallback and Devpost traceability.

Checkpoint: every public claim maps to immutable evidence.

## Execution Rules

- Implement S/M-sized tasks and verify each increment.
- Do not build report polish before the capacity gate.
- UI may develop against frozen fixtures in parallel but cannot claim accepted
  metrics before evidence exists.
- Paid sessions execute only a preregistered task.
