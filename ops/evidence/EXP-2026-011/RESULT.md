# EXP-2026-011 Result

Status under the preregistered gate: **rejected**.

## Completed

- Matched Arm Performix Code Hotspots runs completed and exported natively.
- The same positive/negative KleidiAI attribution observed in EXP-2026-010 was
  reproduced before the next recipe began.
- The instance was terminated and the final AWS inventory was empty.
- Estimated session cost: USD 0.0781; cumulative project estimate: USD 10.9399.

## Failed Gate

The Instruction Mix recipe reported
`tool_integrations.neoprof.INSUFFICIENT_PMU_COUNTERS`: it requires at least
three PMU counters, while CPU 0 exposed two. Execution stopped before System
Utilization, so the preregistered all-recipe requirement did not pass.

This does not rewrite EXP-2026-010. Its successfully completed matched Code
Hotspots exports independently established the narrower execution-attribution
claim used by ArmProof. CPU Microarchitecture and Instruction Mix remain
explicitly unavailable on this virtual PMU; System Utilization is not claimed.

Archive SHA-256:

```text
0607066858a633c38c693bae7f99436f1bc16cda165e0e5c659c39cefdd4a1d4
```
