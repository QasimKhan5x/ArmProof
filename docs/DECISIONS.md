# Architecture Decision Log

Use short append-only entries. Superseded decisions remain visible.

## ADR-001: Build KleidiScope As A New Project

- Date: 2026-07-29
- Status: accepted
- Decision: initialize `~/PersonalProjects/KleidiScope` rather than overwrite
  the unrelated VerifyLane/Committee-of-One repository.
- Reason: the active concept, architecture, users, and evidence are materially
  different. Mixing histories would confuse agents and contributors.

## ADR-002: Local-First, Graviton4 For Hardware Truth

- Date: 2026-07-29
- Status: accepted
- Decision: perform implementation and fixture work locally/free CI, then use
  `c8g.2xlarge` for bounded final experiments with `c8g.4xlarge` fallback.
- Reason: this preserves current Arm hardware, a 3B model, and representative
  CPU inference while keeping expected AWS spend below $10.

## ADR-003: Existing Mixed Quantization Is A Baseline

- Date: 2026-07-29
- Status: accepted
- Decision: compare with upstream `--target-bpw` and do not claim generic
  automatic per-tensor quantization as the invention.
- Reason: current llama.cpp already provides per-tensor overrides and an
  automatic quality/size optimizer. KleidiScope must demonstrate value through
  Arm dispatch observability and hardware-aware performance constraints.

## ADR-004: Evidence-First Architecture

- Date: 2026-07-29
- Status: accepted
- Decision: schemas and immutable evidence bundles precede dashboard and full
  CLI work.
- Reason: judge claims and long-horizon agent correctness require replayable
  evidence independent of conversation state or UI.

## ADR Template

```markdown
## ADR-NNN: Title

- Date: YYYY-MM-DD
- Status: proposed | accepted | superseded | rejected
- Decision:
- Context:
- Alternatives:
- Consequences:
- Evidence/links:
```

