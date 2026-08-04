# ArmProof Reference Decision

This config verifies the checksum-bound sustained archive from
`EXP-2026-009` and the matched Arm Performix archive from `EXP-2026-010`. The
adapter re-derives 4,200 request outcomes, the conservative capacity lower
bound, quality, and Arm execution before building the report without AWS:

```bash
armproof ci examples/armproof-reference/armproof.json
```

The comparison isolates KleidiAI with identical source model, runtime,
workload, environment and thread count. The only causal control is
`kleidiai.enabled`. Raw evidence remains under `ops/evidence/EXP-2026-009/`
and `ops/evidence/EXP-2026-010/`.
