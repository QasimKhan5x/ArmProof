# ArmProof Roadmap

## Phase 0: Context And Evidence Foundation

- Replace stale project context.
- Import and hash accepted result-first evidence.
- Establish verified Python bootstrap commands.
- Freeze contract, evidence and claim schemas.

Gate: existing results verify without reinterpretation.

## Phase 1: Fail-Closed Vertical Slice

- Parse one reference contract.
- Load fixture treatments and evidence.
- Evaluate claim dependencies and thresholds.
- Emit one machine decision and static report.
- Prove missing or swapped evidence fails.

Gate: fixture-to-decision-to-report works end to end.

## Phase 2: Real Service Execution

- Implement common HTTP service adapters.
- Implement workload replay, PSS sampling and quality plugins.
- Add bounded `perf`/Performix attribution.
- Measure ArmProof overhead.

Gate: local/Arm smoke tests prove lifecycle and negative behavior.

## Phase 3: Capacity Validation

- Preregister and run the fixed-SLO experiment on Graviton4.
- Freeze the accepted result and evidence bundle.

Gate: `CAPACITY_VALIDATION.md` passes. Do not manufacture a weaker substitute.

## Phase 4: Community Product

- Build the interactive report against frozen schemas.
- Add the GitHub Action and PR summary.
- Emit the exact passing deployment manifest.
- Publish reference contract, adapter guide and tutorial.

Gate: one YAML and one command produce an understandable decision.

## Phase 5: Reproduction And Submission

- Clean-room Graviton reproduction.
- Browser, accessibility, tamper, security and license checks.
- Three-minute demo and offline backup.
- Devpost submission with claim-to-evidence mapping.

Gate: every public claim resolves to immutable evidence.

## Deferred

- Second runtime adapter.
- vLLM reference path.
- Cross-cloud execution.
- Hosted service.
- Cryptographic signing or formal attestation.
