# Current Status

Last updated: 2026-07-29

## Phase

Project initialization and feasibility design.

## Verified State

- Product concept and claim boundary documented.
- Current upstream `llama-quantize` capabilities researched, including
  `--tensor-type` and `--target-bpw`.
- Graviton4 cost envelope researched.
- No application code, runtime patch, model artifact, or benchmark result yet.
- No paid AWS resource has been provisioned.

## Immediate Next Action

Run Phase 0 source reconnaissance from `ops/work-items.json` against a pinned
`llama.cpp` commit. Confirm that the required dispatch evidence is observable
with a minimal, low-overhead patch before provisioning AWS.

## Current Commands

There are no verified build commands yet. Documentation validation consists of:

```bash
git status --short
python3 -m json.tool ops/work-items.json
python3 -m json.tool schemas/experiment.schema.json
```

Add automated link and traceability validation during Phase 0.

## Open Decisions

- Final public name and whether the existing GitHub repository will be renamed.
- Exact 3B source model, subject to license and ungated download availability.
- Pinned `llama.cpp` and KleidiAI revisions.
- Whether Performix is available without licensing or account friction.
- Whether `c8g.2xlarge` is sufficient for every conversion and evaluation step;
  `c8g.4xlarge` is the approved fallback within the same budget ceiling.

## Known Blockers

- AWS CLI session requires reauthentication before any approved provisioning.
- Real feasibility claims require Graviton4 evidence.

