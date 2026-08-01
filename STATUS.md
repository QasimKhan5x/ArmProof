# Current Status

Last updated: 2026-08-01

## Product

SurgeDesk is the judge-facing banking-support application. It routes recorded
BANKING77 requests through human confirmation, replays the accepted
same-instance Graviton surge, and hands off to ArmProof for causal release
proof. ArmProof remains the reusable fail-closed CI gate and evidence engine.

## Accepted Result

The decisive reference gate passed on AWS Graviton4 `c8g.4xlarge`:

- KleidiAI fixed-SLO capacity: 3.0x short, 2.5x long and 3.0x mixed traffic.
- Quality delta: -0.390 percentage points accuracy and -0.673 points macro F1,
  both inside the preregistered one-point tolerance.
- Schema validity: 100% across the 770-item BANKING77 evaluation.
- Operational queue guard: 86.75% held-out five-destination accuracy (668/770), up
  12.34 percentage points from direct LLM intent-to-queue mapping.
- Arm attribution: `kai_*` callchains appear only in the enabled profile.
- Whole deployment: 35.92% less disk, 55.34% lower peak PSS and 59.66% lower
  time-weighted PSS than the BF16 reference.
- Clean reproduction: all three capacity ratios matched exactly on a fresh
  `c8g.4xlarge`, with the same quality gate and enabled-only `kai_*` evidence.

The corrected capacity result is `EXP-2026-004`. The aborted and inconclusive
attempts remain preserved and visible.

## Product State

Completed: guarded AWS lifecycle, reference service, fixed-SLO harness, policy
engine, pass/fail/unknown fixtures, single-config CLI, reusable GitHub Action,
responsive offline report, integrity verifier and pinned deployment artifact.

The SurgeDesk workflow now includes a held-out two-stage queue guard, human
confirm/correct state machine, equal-load customer-outcome replay, confirmed
capacity boundary, release-proof view, executable adoption path and optional
live Graviton gateway. Recorded mode refuses to present edited text as
inference; live mode remains disabled unless a trusted endpoint is configured.

Version `v0.2.0` is the current public release. Native Arm64,
x86 and report-browser CI pass on the release commit, and the public example
Action passes while uploading its decision and offline report. Remaining
submission work is the hackathon video and final Devpost packaging. The
secondary measurement-overhead claim remains unpublished until it has a
matched baseline.

## Verified Commands

```bash
make check
armproof ci examples/armproof-reference/armproof.json
armproof evidence-verify \
  --checksums ops/evidence/EXP-2026-004/accepted/evidence/SHA256SUMS \
  --root ops/evidence/EXP-2026-004/accepted/evidence
npm run test:ui
```

## Constraints

- Accepted performance claims are scoped to the pinned Phi-4 Mini workload,
  runtime and `c8g.4xlarge`; they are not universal model claims.
- Project source is MIT licensed; BANKING77 is attributed under CC-BY-4.0.
- Estimated cumulative AWS evidence cost is USD 3.8689 and inventory is empty.
- ArmProof means "verified against the declared contract," not Arm certified.
