# Current Status

Last updated: 2026-08-05

## Product

SurgeDesk is the judge-facing banking-support application. A real customer
message is classified by Phi-4 Mini on a CPU-only Graviton4 service, a person
chooses the final support queue, and the resulting ticket records the serving
lane. The application begins on the KleidiAI-disabled lane. It can activate the
optimized lane only after ArmProof re-derives the measured release and confirms
that both running services match the audited model, verified runtime artifacts,
AWS instance type, Arm shape, thread count, affinity, and treatment control.
Every optimized response is checked again, and drift restores the control route.

ArmProof is the reusable component: a Python CLI, evidence-adapter interface,
offline report, GitHub Action, fixed-rate HTTP harness, native Performix parser,
and `armproof init` starter generator for other bounded Arm AI services.

## Accepted Release

The final capacity release is `EXP-2026-014`, run on one AWS Graviton4
`c8g.4xlarge` with 16 threads and a ten-second p95 SLO.

- KleidiAI-disabled control at 0.28 requests/s: all five 500-second windows failed.
- KleidiAI-enabled treatment at 0.56 requests/s: all five windows passed.
- Released lower bound: `0.56 / 0.28 = at least 2.0x` sustainable traffic.
- Evidence volume: 2,100 raw scheduled-request records and 1,540 raw model outputs.
- Quality: -0.390 percentage points accuracy, -0.673 points macro F1, and 100% schema validity.
- Native Arm Performix: 0% `kai_*` function samples in the control and 67.35% in the treatment, including the Neoverse I8MM matrix kernel.
- Linux perf, kept as a separate unit, measured 67.91% KleidiAI cycle attribution in the treatment and 0% in the control.
- Separate BF16-to-INT4 migration: 35.92% smaller files, 55.34% lower peak PSS, and 59.66% lower time-weighted PSS.
- SurgeDesk queue guard: 86.75% held-out five-queue accuracy versus 74.42% for direct LLM intent mapping; this is a product-quality result, not an Arm speed claim.

All ten required claims pass. The Git object `ab22cc0` contains the exact plan
bytes and its time predates the recorded instance-launch and measurement times.
The same bytes are present in the prelaunch project bundle and final measurement
archive. The launch timestamp is recorded experiment metadata rather than
independent cloud attestation. The rejected
identity-incomplete `EXP-2026-012` and earlier discovery runs remain visible but
cannot approve this release.

## Verification State

- `armproof ci examples/armproof-reference/armproof.json` passes and generates the public report from raw evidence.
- 192 Python tests pass; one optional localhost-connectivity test is skipped by design.
- 6 JavaScript behavior tests pass.
- 8 Playwright workflows pass across desktop, tablet, and 320-pixel mobile.
- The real localhost end-to-end test runs a control-plus-shadow comparison,
  recalculates the audit, binds deployment data, activates the optimized lane,
  routes the next request through it, and proves post-release drift fails closed.
- Static UI source contains no measured result literals, fake timers, tampering scene, or rejected 2.5x claim.
- The generated adoption ZIP contains 16 files, an explicit evidence layout and a GitHub Action bound to its parsed contract digest; `armproof seal` creates the portable evidence ledger after collection.
- AWS cumulative evidence cost is estimated at `$13.4872`; the final inventory is empty.

## Demo Boundary

The recording uses a live control-plus-shadow comparison before activation and
a different live request after activation. The ten long capacity windows and
matched Performix profiles were collected earlier because they require more
than three minutes; the video visibly reruns their verification from checked-in
raw archives. The app labels the one-request timing as illustrative and keeps it
separate from the sustained-capacity claim.

## Remaining Owner Work

The repository, public artifacts, screenshots, submission copy, and recording
runbook are ready for the `v0.9.0` release. The owner must record and publicly
upload the video, replace the Devpost video placeholder, paste the prepared
submission, and complete the logged-out link check.

## Constraints

- Results apply to the pinned Phi-4 Mini INT4 model, workload, ONNX Runtime GenAI build, 16-thread Graviton4 deployment, and fixed response-time rule.
- Performix CPU Microarchitecture and Instruction Mix recipes were unavailable because the VM exposed two PMU counters while those recipes require three.
- ArmProof means verified against the declared contract; it is not Arm certification.
- Project source is MIT licensed. BANKING77 is attributed under CC BY 4.0.
