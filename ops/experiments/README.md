# Experiment Registry

`registry.jsonl` is ArmProof's append-only experiment history. Each experiment
receives an ID such as `EXP-2026-001`, a preregistration conforming to
[`schemas/experiment.schema.json`](../../schemas/experiment.schema.json), and
an immutable evidence directory.

Historical experiments performed before ArmProof was named are imported, not
rewritten. Preserve failed or unfavorable outcomes and append a superseding
record when a protocol changes.

The registry is an index, not the evidence itself. A claim is publishable only
when its record points to a complete, checksummed bundle.
