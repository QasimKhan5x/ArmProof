# Confirmed ArmProof Reference

This reference is the release gate used by SurgeDesk. It combines:

- the identity-bound two-rate capacity confirmation from `EXP-2026-014`;
- the 1,540 original quality outputs captured in `EXP-2026-003`; and
- the matched native Arm Performix profiles from `EXP-2026-013`.

Run it from the repository root:

```bash
armproof ci examples/armproof-reference/armproof.json
```

The `kleidiai-confirmed-v2` adapter reads the two committed preregistrations,
recalculates ten 500-second capacity windows, reparses the raw model outputs,
checks the model/runtime/workload/treatment identities, derives native Performix
function-sample attribution, and evaluates the ten claims in
`confirmed-contract.json`.

The capacity rates and Performix thresholds come from the preregistration files,
not from `armproof.json`. Changing a rate, threshold, treatment config, run ID,
workload, raw response or profiler export blocks the release.

Historical EXP-2026-009 and EXP-2026-010 evidence remains in the repository as
discovery history. EXP-2026-012 matched the frozen performance outcome but is
also excluded because its successful responses omitted the preregistered
source-artifact identity. None of those archives can approve this release.
