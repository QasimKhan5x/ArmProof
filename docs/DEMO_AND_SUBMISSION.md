# Demo And Submission Plan

The demo is a realistic developer workflow, not an invented application layer.

## Scenario

An inference engineer has deployed a 3B instruct model on Graviton4 with
`llama.cpp` and KleidiAI. The model runs, but the developer cannot explain
whether the important operations are accelerated or whether the standard GGUF
is the right artifact for this Arm machine.

## Three-Minute Demo

### 0:00-0:20 - Problem And Input

Show the real GGUF, pinned workload, Graviton4 identity, and one baseline
performance result. State the problem plainly: enabling a backend does not
explain coverage or produce the best deployable model.

### 0:20-0:55 - Execution X-Ray

Run or replay `kleidiscope record` and open the report:

- model execution paths are weighted by measured significance;
- accelerated paths identify KleidiAI kernel/family and ISA requirement;
- fallbacks show stable reason codes and source-grounded explanations;
- unknown attribution remains visible.

Select one expensive fallback and show the tensor, type, shape, source rule,
and why a candidate format is eligible.

### 0:55-1:25 - Explainable Optimization

Run or replay `kleidiscope optimize`:

- declare quality and size/performance constraints;
- show no more than three candidate recipes;
- show the rationale for each tensor override;
- distinguish KleidiScope policy from upstream `llama-quantize` execution.

### 1:25-2:15 - Controlled Comparison

Show the comparison table/frontier for:

- F16/BF16 quality reference;
- Q4_K_M;
- relevant standard/uniform quant;
- size-matched target-BPW;
- KleidiScope candidate.

Headline only measured outcomes: quality, bytes/RSS, PP/TG, TTFT/p95, and
coverage with uncertainty.

### 2:15-2:40 - Reusable Artifact

Download or open:

- recipe and exact quantizer command;
- candidate checksum/model reference;
- trace schema and fallback rules;
- evidence manifest and reproduction command;
- CI regression check.

### 2:40-3:00 - Contribution

Conclude with the scoped measured result and community value: an Arm developer
can inspect, optimize, reproduce, and guard a model without repeating source
archaeology.

## UX Requirements

- First screen answers: what won, by how much, on what hardware, under what
  quality constraint.
- The X-ray is a functional inspection view, not decoration.
- Tooltips explain unfamiliar kernel/ISA terms.
- Failed and inconclusive candidates remain accessible.
- Every chart links to raw values and environment identity.
- No nested card-heavy dashboard or marketing landing page.
- Desktop and mobile text never overlap; dense tables adapt to narrow screens.
- A fixture-backed offline mode guarantees the demo without a live AWS bill.

## Submission Artifacts

- Public source repository.
- Three-minute video and optional longer technical walkthrough.
- Interactive static report hosted without a running inference server.
- Optimized model when license permits, otherwise recipe and reproducible build.
- Raw evidence bundle with checksums.
- Technical architecture and benchmark methodology.
- Arm optimization tutorial.
- Upstream patch or contribution-ready diff.
- Judge quickstart requiring no cloud spend for report inspection.

## Backup Story If The Speed Gate Fails

Do not manufacture a win. A PIVOT submission is viable only if KleidiScope
still provides uniquely useful, accurate kernel/fallback observability and
demonstrates a defensible size/quality or developer-workflow improvement. The
submission must state that the tested candidate did not improve speed.

If neither optimization nor actionable observability survives, do not submit
this concept as though it succeeded.

