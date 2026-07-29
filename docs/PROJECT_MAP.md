# Project Map

Use this page to load the smallest useful context set.

| Question or task | Read |
|---|---|
| What are we building and why? | `CONCEPT.md` |
| What must the system do? | `REQUIREMENTS.md` |
| What makes this competitive? | `JUDGING_STRATEGY.md` |
| Is the central mechanism feasible? | `FEASIBILITY_PLAN.md`, `BENCHMARK_PROTOCOL.md` |
| How should components fit together? | `ARCHITECTURE.md` |
| What should be built next? | `ROADMAP.md`, `../ops/work-items.json`, `../STATUS.md` |
| How are claims accepted? | `TRACEABILITY.md`, `BENCHMARK_PROTOCOL.md` |
| How is AWS spending controlled? | `AWS_BUDGET.md` |
| What can invalidate the project? | `RISKS.md` |
| How should a fresh agent resume? | `AGENT_PLAYBOOK.md`, `../AGENTS.md` |
| What is shown to judges? | `DEMO_AND_SUBMISSION.md` |
| Why was a decision made? | `DECISIONS.md` |
| Which external facts support this? | `SOURCES.md` |

## Durable Versus Mutable State

Stable intent belongs in `docs/`. Mutable execution state belongs in:

- `STATUS.md`: compact human handoff and next action.
- `ops/work-items.json`: machine-readable phase and verification status.
- `ops/experiments/registry.jsonl`: append-only experiment index.
- `ops/evidence/<run-id>/`: immutable raw evidence bundles.

Do not store benchmark truth only in conversation history, screenshots, or a
dashboard. Reports are projections of the evidence bundle.

## Planned Code Layout

The following layout is architectural intent and should be created
incrementally:

```text
src/kleidiscope/       CLI, orchestration, policies, reports
patches/llama.cpp/     minimal pinned tracing patch or integration
schemas/               trace, recipe, comparison, experiment schemas
workloads/             pinned prompt and server workloads
evaluation/            quality and performance adapters
tests/                 unit, contract, integration, golden-fixture tests
scripts/               bootstrap, reproduce, AWS lifecycle, cleanup
ops/                    work state, experiments, evidence
docs/                   stable decisions and user-facing engineering docs
```

