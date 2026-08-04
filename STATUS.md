# Current Status

Last updated: 2026-08-04

## Product

SurgeDesk is the judge-facing banking-support application. It routes recorded
BANKING77 requests through human confirmation, replays the accepted
same-instance Graviton surge, and hands off to ArmProof for causal release
proof. ArmProof remains the reusable fail-closed CI gate and evidence engine.

## Accepted Result

The decisive sustained audit ran on AWS Graviton4 `c8g.4xlarge`:

- Public fixed-SLO claim: at least 2.0x higher sustainable mixed traffic.
- Tested pass points: disabled 0.24 r/s and enabled 0.56 r/s, each passing all
  five 500-second confirmations; tested pass-point ratio 2.33x.
- Baseline 0.28 r/s failed all five windows, establishing the 2.0x lower bound.
- The original exact 2.5x bracket was rejected because enabled 0.60 r/s passed
  one of five windows. This rejected gate remains public.
- Quality delta: -0.390 percentage points accuracy and -0.673 points macro F1,
  both inside the preregistered one-point tolerance.
- Schema validity: 100% across the 770-item BANKING77 evaluation.
- Operational queue guard: 86.75% held-out five-destination accuracy (668/770), up
  12.34 percentage points from direct LLM intent-to-queue mapping.
- Arm attribution: 68.53% of sampled cycles reached the enabled KleidiAI I8MM
  callchain, versus 0% disabled, with zero lost samples.
- Arm Performix 1.20 independently measured 67.02% `kai_*` function samples
  enabled versus 0% disabled. The 1.51 pp difference from Linux perf is inside
  the frozen 5 pp agreement limit.
- Whole deployment: 35.92% less disk, 55.34% lower peak PSS and 59.66% lower
  time-weighted PSS than the BF16 reference.
- Earlier short-window evidence reproduced on a fresh instance but is retained
  as supporting history, not the public sustained-capacity headline.

The public sustained result is derived from `EXP-2026-009`. That experiment is
marked rejected under its original exact-bracket gate; only its independently
supported conservative lower bound is released. All failed and inconclusive
attempts remain preserved and visible.

## Product State

Completed: guarded AWS lifecycle, reference service, fixed-SLO harness, policy
engine, pass/fail/unknown fixtures, single-config CLI, reusable GitHub Action,
responsive offline report, integrity verifier and pinned deployment artifact.

The reference release path verifies 317 files across the primary,
fresh-instance and native Arm Performix bundles, re-derives capacity, quality
and matched Code Hotspots attribution, binds model,
runtime, workload, environment and treatment identities to the contract, and
only then evaluates eight required claims. Caller-authored normalized
comparisons are rejected by `armproof ci`. The report emits a verification
receipt, and the safe tamper challenge proves one changed ledger digest blocks
before policy evaluation.

SurgeDesk includes a held-out queue guard, human confirmation, equal-load
replay, sustained lower bound, rejected overclaim, release proof and optional
live gateway. Recorded mode rejects edited text rather than presenting it as
inference.

`armproof init` scaffolds a runtime-neutral HTTP evidence project and fails
closed until real evidence is supplied. A llama.cpp/Qwen2.5 0.5B Q4_0 bridge
completed a local Arm64 compatibility smoke without a performance claim.

The c8g.4xlarge virtual PMU exposed two counters. Performix CPU
Microarchitecture and Instruction Mix each require at least three, so those
readiness failures remain public and unavailable rather than passing.

Version `v0.6.0` is the Performix-integrated release candidate pending tag and
remote CI.
Native Arm64, x86 and report-browser CI cover the Action, decision and offline
report. Submission copy and the under-three-minute script are under
`submission/`. Remaining owner work is recording/uploading the video and
pasting the prepared entry into Devpost. Measurement overhead remains
unpublished until it has a matched baseline.

## Verified Commands

```bash
make check
armproof ci examples/armproof-reference/armproof.json
python3.12 scripts/demo_release_gate.py
armproof evidence-verify \
  --checksums ops/evidence/EXP-2026-004/accepted/evidence/SHA256SUMS \
  --root ops/evidence/EXP-2026-004/accepted/evidence
npm run test:ui
python3.12 scripts/demo_live_compare.py --help
.venv/bin/armproof init --endpoint http://127.0.0.1:8000/infer --output KIT
```

## Constraints

- Accepted performance claims are scoped to the pinned Phi-4 Mini workload,
  runtime and `c8g.4xlarge`; they are not universal model claims.
- Project source is MIT licensed; BANKING77 is attributed under CC-BY-4.0.
- Estimated cumulative AWS evidence cost is USD 10.9399 and inventory is empty.
- ArmProof means "verified against the declared contract," not Arm certified.
