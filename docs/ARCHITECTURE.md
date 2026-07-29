# Evolving Architecture

The architecture grows only after each feasibility gate. Interfaces are
versioned JSON contracts so the runtime integration, policy engine, and report
can evolve independently.

## System Context

```text
Developer
   |
   v
KleidiScope CLI/orchestrator
   |-- target probe
   |-- patched/pinned llama.cpp recorder
   |-- source-rule analyzer
   |-- recipe policy
   |-- upstream quantizer adapter
   |-- evaluation runners
   `-- evidence/report generator
            |
            v
      immutable evidence bundle
```

## Stage 0: Experimental Harness

Purpose: prove observability and optimization potential with scripts and stable
schemas before designing a full application.

Components:

- `target-probe`: captures environment and CPU features.
- `trace-hook`: minimal instrumentation in the pinned execution path.
- `trace-normalizer`: converts events to the versioned trace schema.
- `rule-inventory`: source-revision-specific dispatch/fallback rules.
- `recipe-notebook-or-script`: bounded candidate generation.
- `experiment-runner`: invokes quantizer, quality, and benchmark commands.
- `evidence-writer`: writes immutable run bundles.

Stage 0 may be inelegant internally, but its outputs cannot be ad hoc.

## Stage 1: MVP Architecture

```text
kleidiscope record
  -> environment probe
  -> workload adapter
  -> runtime process
  -> trace events
  -> normalized run.json

kleidiscope explain
  -> source rule provider
  -> coverage aggregator
  -> ranked fallback report

kleidiscope optimize
  -> constraints
  -> candidate policy
  -> recipe.json + rendered quantizer command

kleidiscope compare
  -> candidate builder
  -> quality runner
  -> performance runner
  -> decision gate
  -> comparison.json
```

The MVP supports one pinned runtime family, one 3B model architecture, one Arm
target family, and one quality adapter. Unsupported combinations fail clearly.

## Stage 2: Full Hackathon Product

### CLI And Orchestrator

Responsibilities:

- validate prerequisites and architecture;
- assign run IDs;
- enforce phase transitions and budgets;
- invoke subprocesses without shell interpolation;
- stream progress and preserve diagnostics;
- resume safe idempotent steps;
- generate reproduction commands.

### Runtime Integration

Responsibilities:

- emit bounded structured events;
- identify operation, tensors, types, shapes, backend, dispatch result, and
  kernel identifier/family where observable;
- emit stable reason codes rather than English-only messages;
- remain disabled by default;
- expose sampling/aggregation if event volume is high.

This integration should be a small patch or upstream-compatible hook. The
orchestrator must pin the exact source revision it understands.

### Source Rule Provider

Responsibilities:

- map normalized runtime facts to eligibility/fallback rules;
- include source revision and location;
- distinguish observed, derived, and unknown facts;
- reject incompatible runtime versions;
- allow fixtures independent of live inference.

Rules are data or narrow adapters, not prose scraped at runtime.

### Coverage Aggregator

Produces:

- event-count coverage;
- tensor-byte-weighted coverage;
- observed-duration-weighted coverage;
- prompt versus decode breakdown;
- ranked fallback groups;
- unknown/unattributed proportions.

Never present sampled profiler time as exact per-operation time unless the
correlation mechanism is tested.

### Recipe Policy Engine

Inputs:

- tensor inventory and current formats;
- runtime-weighted opportunities;
- CPU/kernel compatibility matrix;
- quality sensitivity/imatrix data;
- target size/BPW and quality budget;
- candidate-count and wall-time budgets.

Outputs:

- ordered override rules;
- rationale per override;
- predicted size/BPW;
- expected dispatch effect;
- uncertainty and exclusions;
- rendered upstream command.

The first policy should be deterministic heuristics. A learned optimizer is out
of scope until evidence proves heuristics inadequate.

### Quantizer Adapter

Responsibilities:

- verify source model precision;
- reject accidental requantization by default;
- invoke pinned `llama-quantize` arguments;
- capture complete execution evidence;
- inspect output tensor distribution;
- hash inputs, recipe, tool, and output.

### Evaluation Layer

Adapters:

- model size and GGUF inspection;
- process RSS and peak RSS;
- `llama-bench` prompt/decode measurements;
- `llama-server` fixed-load measurements;
- perplexity/KLD and optional task-quality measurement;
- optional Performix capture as corroborating evidence.

Evaluation consumes candidates; it does not know how they were generated.

### Evidence Store

An evidence bundle is a directory, not a database dependency:

```text
ops/evidence/<run-id>/
  manifest.json
  environment.json
  commands.jsonl
  trace.jsonl.zst
  coverage.json
  recipes/
  measurements/
  logs/
  checksums.txt
  decision.json
  report-data.json
```

Large model files remain external but are referenced by checksum and license.

### Report Application

Views:

1. verdict and headline Pareto comparison;
2. model execution X-ray;
3. ranked fallbacks and source-grounded explanations;
4. candidate recipe diff;
5. quality, size, memory, PP/TG, TTFT, p50/p95, and uncertainty;
6. environment and Arm/KleidiAI proof;
7. reproduction and raw evidence downloads.

The report must render completely from fixture data for browser testing.

### CI Interface

The CI command compares a candidate evidence bundle with a committed baseline
policy and emits:

- machine-readable result;
- human summary;
- stable exit code;
- inconclusive status for noisy or missing evidence.

## Public Contracts

Version these independently:

- trace event schema;
- environment manifest;
- source rule schema;
- recipe schema;
- measurement schema;
- comparison/decision schema;
- evidence bundle manifest.

Breaking changes require migration notes and an ADR.

## Error Model

Use typed categories:

- `unsupported_architecture`
- `runtime_revision_mismatch`
- `kernel_mapping_unknown`
- `source_model_not_high_precision`
- `quality_budget_failed`
- `performance_inconclusive`
- `candidate_build_failed`
- `cloud_budget_exceeded`
- `partial_evidence`

An error must preserve the command, diagnostics, partial artifacts, and next
corrective action.

## Technology Direction

- Python 3.12 for CLI, orchestration, schemas, and evaluation adapters.
- Typer or Click for CLI only after a minimal comparison; avoid framework
  dependence in domain logic.
- Pydantic or JSON Schema for boundary validation.
- `llama.cpp` C/C++ minimal patch for runtime events.
- Existing `llama-quantize`, `llama-bench`, `llama-perplexity`, and
  `llama-server` tools.
- Static React/TypeScript report only if plain generated HTML cannot meet the
  interaction requirement; choose after the feasibility result.
- Pytest and property-based tests for policy and contracts.
- GitHub Actions Arm64 standard runner for free integration coverage.
- AWS C8g for final performance evidence.

Dependencies must be pinned after source reconnaissance. This document does
not authorize inventing an API before verifying upstream.

