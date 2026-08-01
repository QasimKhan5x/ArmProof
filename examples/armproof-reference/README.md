# ArmProof Reference Decision

This config, contract and comparison are normalized from accepted experiment
`EXP-2026-004`. Verify them and build the report without AWS:

```bash
armproof ci examples/armproof-reference/armproof.json
```

The comparison isolates KleidiAI with identical source model, runtime,
workload, environment and thread count. The only causal control is
`kleidiai.enabled`. Raw evidence remains under
`ops/evidence/EXP-2026-004/accepted/`.
