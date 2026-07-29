# KleidiScope

KleidiScope is an Arm-aware profiler and mixed-quantization optimizer for
GGUF models running through `llama.cpp` and KleidiAI on Arm CPUs.

It answers two questions that existing startup logs and generic quantizers do
not answer together:

1. Which model operations and tensor formats actually reach optimized
   KleidiAI microkernels on this Arm machine, and why do the others fall back?
2. Can the model's tensor formats be changed to improve the measured
   size-quality-speed tradeoff on that machine?

The intended workflow is:

```text
GGUF model + pinned workload + Arm target
                    |
                    v
       structured dispatch and fallback trace
                    |
                    v
         weighted acceleration coverage report
                    |
                    v
       bounded hardware-aware quantization recipes
                    |
                    v
  candidate GGUFs + quality/performance/server evaluation
                    |
                    v
 optimized artifact + reproducible evidence + HTML report
```

The proposed CLI contract is:

```bash
kleidiscope record --model model.gguf --workload workload.jsonl
kleidiscope explain --trace run.json
kleidiscope optimize --trace run.json --quality-budget 0.01
kleidiscope compare --baseline baseline.gguf --candidate candidate.gguf
kleidiscope report --evidence evidence/run-id
```

These commands are product requirements, not claims of current implementation.
The repository starts in the feasibility phase.

## Contribution Boundary

`llama.cpp` already supports per-tensor `--tensor-type` overrides and a
quality-oriented `--target-bpw` optimizer. KleidiScope must not rebrand those
features. Its intended contribution is the integration of:

- source-grounded Arm/KleidiAI dispatch observability;
- explicit eligibility and fallback explanations;
- runtime-weighted kernel coverage;
- hardware-aware candidate selection under declared quality and size budgets;
- reproducible comparisons against both standard presets and upstream
  `--target-bpw` optimization; and
- CI and reporting artifacts that Arm developers can reuse.

## Success Gate

Before building the full product, one generated candidate must demonstrate on
real Graviton4 hardware either:

- at least 10% improvement in a primary speed metric while meeting the quality
  budget; or
- at least 10% reduction in disk/RSS while speed regresses by no more than 3%
  and the quality budget is met.

It must also beat or add demonstrably useful information beyond the matched
`--target-bpw` baseline. Failure is a valid feasibility result; fabricated or
selectively reported success is not.

## Start Here

- Current state: [`STATUS.md`](STATUS.md)
- Project map: [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md)
- Concept: [`docs/CONCEPT.md`](docs/CONCEPT.md)
- Requirements: [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md)
- Feasibility gate: [`docs/FEASIBILITY_PLAN.md`](docs/FEASIBILITY_PLAN.md)
- Agent operating rules: [`AGENTS.md`](AGENTS.md)

## Status

Documentation and experiment design are being initialized. No benchmark or
optimization result is currently claimed.

