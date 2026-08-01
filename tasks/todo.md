# ArmProof Task Checklist

- [x] **CTX-001: Replace stale project context**
  - Acceptance: active docs describe ArmProof; retired concept survives only as
    historical decision context.
  - Verify: `python3 scripts/validate_context.py`.

- [x] **EVID-001: Import established result-first evidence**
  - Acceptance: immutable manifest, checksums and separate experiment records.
  - Verify: manifest/hash tests and traceability paths resolve.
  - Context: `context/packs/EVID-001.md`.

- [x] **BOOT-001: Establish Python project commands**
  - Acceptance: install, format, lint, unit and smoke commands work cleanly.
  - Verify: execute each command and update `AGENTS.md`/`STATUS.md`.

- [x] **SCHEMA-001: Freeze public contracts**
  - Acceptance: contract, evidence and claim schemas plus valid/invalid fixtures.
  - Verify: missing identities and required evidence fail.

- [x] **CORE-001: Implement fail-closed claim ledger**
  - Acceptance: causal scopes, thresholds, dependencies and reason codes.
  - Verify: tamper, unknown, mismatch and unfavorable-result tests.

- [x] **FIXTURE-001: Complete evidence-to-report slice**
  - Acceptance: existing evidence produces one verified decision and basic
    static report.
  - Verify: CLI, JSON and report agree; offline generation succeeds.

- [x] **DATA-001: Freeze public reference workload**
  - Acceptance: license, IDs, hashes, parser and traffic mixes recorded.
  - Verify: deterministic download and at least 500 labeled examples.

- [x] **QUALITY-001: Implement quality adapter**
  - Acceptance: absolute metric, non-inferiority and malformed-output handling.
  - Verify: golden output and regression fixtures.

- [x] **AWS-001: Update dry-run lifecycle and cost guard**
  - Acceptance: ArmProof tags, TTL, non-root guard, inventory and cleanup.
  - Verify: dry run creates no resources.

- [x] **SERVICE-001: Implement common HTTP treatment adapters**
  - Acceptance: BF16, INT4 disabled and INT4 enabled expose one interface.
  - Verify: readiness, timeout, shutdown and config-diff tests.

- [x] **LOAD-001: Implement fixed-SLO load and resource runner**
  - Acceptance: traffic replay, RPS, p50/p95/p99, errors and PSS samples.
  - Verify: synthetic server fixtures and overhead measurement.

- [x] **CAP-001: Run fixed-SLO Graviton validation**
  - Acceptance: complete preregistered evidence and pass/fail/inconclusive.
  - Verify: `docs/CAPACITY_VALIDATION.md` and clean resource inventory.
  - Context: `context/packs/CAP-001.md`.

- [x] **REPORT-001: Build interactive evidence report**
  - Acceptance: decision, causal map, capacity, quality and Arm evidence views.
  - Verify: browser, accessibility, responsive and failed-state tests.

- [x] **ACTION-001: Ship GitHub PR gate**
  - Acceptance: reusable Action posts the verified decision and artifacts.
  - Verify: enabled pass and disabled failure on a test PR.

- [x] **DEPLOY-001: Emit exact passing deployment**
  - Acceptance: manifest pins the measured treatment without reconstruction.
  - Verify: manifest identity matches claim ledger treatment.

- [x] **REPRO-001: Clean-room reproduction**
  - Acceptance: clean Graviton run within 10% using public instructions.
  - Verify: evidence, spend and cleanup records.

- [x] **DEMOAPP-001: Build the SurgeDesk application demo**
  - Acceptance: held-out two-stage triage, equal-load replay, optional live
    Graviton request and ArmProof proof form one evidence-backed workflow.
  - Verify: 85% queue gate, generated-data drift, logic, live-mode browser and
    320-pixel layout tests.

- [ ] **SHIP-001: Harden and submit**
  - Acceptance: public artifacts, demo, licenses, scans and Devpost mapping.
  - Verify: every submission claim resolves to traceability evidence.
  - Complete: public `v0.1.0`, x86/Arm64/report CI and live example Action.
  - Remaining: record the demo video and submit the final Devpost entry.
