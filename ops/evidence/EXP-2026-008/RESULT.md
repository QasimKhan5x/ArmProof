# EXP-2026-008 Result: Rejected

EXP-2026-008 completed cleanly but failed its preregistered acceptance gate.
All 103 relocated checksums verify, all 37 measurement windows used unique
processes and successful warmups, and AWS cleanup is complete.

## Valid findings

- Disabled control: 0.24 requests/s passed and 0.28 requests/s failed in all
  five 500-second confirmations.
- Enabled treatment: 0.60 requests/s failed all five confirmations, with p95
  latency from 12.18 to 13.90 seconds against the frozen 10-second SLO.
- Quality remained within one percentage point on 770 frozen rows.
- Enabled profiling attributed 68.31% of sampled cycles to the KleidiAI I8MM
  matmul callchain; the disabled control attributed 0%, with zero lost samples.
- The matched model overlays differ only in `mlas.disable_kleidiai`.

The generated diagnostic ratio and bracket are unavailable because the enabled
passing boundary was not valid. EXP-2026-009 separately confirms the promising
0.56 requests/s point; no 2.5x sustained-capacity claim is derived from this run.

## Audit

- Evidence archive SHA-256: `b77ac91477bb51d0f4514ee14b205521b080bce2cd59427c9e6b042de4f97317`
- Session cost: `$2.4518`
- Cumulative project cost: `$8.8144`
- Instance terminated; post-run AWS inventory empty
