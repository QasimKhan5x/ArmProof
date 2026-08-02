# ArmProof Reference Decision

This config verifies checksum-bound raw evidence from accepted experiment
`EXP-2026-004`. The adapter derives the comparison and builds the report without
AWS:

```bash
armproof ci examples/armproof-reference/armproof.json
```

The comparison isolates KleidiAI with identical source model, runtime,
workload, environment and thread count. The only causal control is
`kleidiai.enabled`. Raw evidence remains under
`ops/evidence/EXP-2026-004/accepted/`.
