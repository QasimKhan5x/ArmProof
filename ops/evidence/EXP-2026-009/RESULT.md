# EXP-2026-009 Result

Decision: **REJECTED as preregistered; conservative sub-claim established**

The exact `2.0x-2.5x` capacity-ratio bracket was not established because the
KleidiAI-enabled `0.60 r/s` failure probe passed one of five 500-second
confirmations by 72 ms. ArmProof therefore emitted no exact ratio or bracket.

The same immutable evidence independently establishes a narrower result:

- KleidiAI disabled passed `0.24 r/s` in all five 500-second windows and failed
  `0.28 r/s` in all five.
- KleidiAI enabled passed `0.56 r/s` in all five 500-second windows with zero
  errors and p95 latency from `3.280 s` to `3.306 s`.
- The tested pass-point ratio is `0.56 / 0.24 = 2.33x`.
- The release adapter re-derives all 4,200 raw request samples across the 20
  confirmation files and rejects any disagreement with stored summaries.
- Because the baseline failed at `0.28 r/s`, the identifiable sustained-capacity
  improvement is at least `0.56 / 0.28 = 2.0x`.
- Quality remained inside the frozen one-percentage-point tolerance and schema
  validity remained 100%.
- The enabled profile attributed 68.53% of cycles to the KleidiAI I8MM matmul
  callchain; the disabled profile attributed 0%, with zero lost samples.

The public product claim is therefore **at least 2.0x sustainable capacity**, not
an exact maximum-capacity estimate. The original failed 2.5x gate remains visible.

Archive SHA-256:
`f22e647aabe40eefd2abc5548306f40e2a5558ce1a85bc31c18319e6e51d78da`

AWS session cost was `$1.9734`; cumulative measured project spend was `$10.7878`.
The instance terminated and post-run inventory was empty.
