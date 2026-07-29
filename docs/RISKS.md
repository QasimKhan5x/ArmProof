# Risks, Assumptions, And Kill Criteria

Risks are ordered by probability times project impact.

## R-01 Existing Upstream Optimizer Dominates

**Assumption:** Arm-kernel-aware policy adds value beyond upstream target-BPW.

**Risk:** target-BPW already yields equal quality/size and equal or better Arm
performance, leaving no optimization contribution.

**Early test:** matched-BPW target-BPW baseline in feasibility.

**Mitigation:** distinguish measured kernel coverage and fallback explanation;
focus policy on performance constraints target-BPW does not model.

**Kill/pivot:** if no candidate advantage or actionable observability remains,
drop the optimizer claim or stop.

## R-02 Dispatch Evidence Is Too Coarse

**Assumption:** pinned runtime source exposes or can cheaply emit operation,
tensor, and kernel decisions.

**Risk:** only backend buffer allocation is visible, making the X-ray misleading.

**Early test:** source reconnaissance plus KleidiAI-on/off trace fixture.

**Mitigation:** narrow granularity to directly observable kernel family or
eligibility class; label derived facts.

**Kill/pivot:** do not advertise per-kernel execution without evidence.

## R-03 Tensor Format Does Not Improve End-To-End Speed

**Assumption:** repairing important fallbacks changes measured performance.

**Risk:** other bottlenecks dominate, or a smaller format increases conversion
overhead.

**Early test:** baseline format matrix before policy implementation.

**Mitigation:** rank by runtime weight; preserve no-change outcome; consider
memory/quality Pareto result.

**Kill/pivot:** stop optimization build if the surface is not measurable.

## R-04 Small Model Is Unconvincing

**Assumption:** a 3B model is representative enough for hackathon proof.

**Risk:** judges view results as toy-scale.

**Mitigation:** use the same 3B shape demonstrated in Arm learning material,
show production server metrics, and make tooling model-independent.

**Kill/pivot:** do not downgrade to 0.5B for final evidence solely to fit free
hardware.

## R-05 Benchmark Noise Or Bias

**Risk:** shared-cloud variance, warmup, order effects, or tracing overhead
manufacture the apparent win.

**Mitigation:** preregistration, randomized/counterbalanced order, warmups,
repeats, raw samples, uncertainty, trace-off headline runs, clean reproduction.

**Kill/pivot:** mark inconclusive when the target effect is not separable.

## R-06 Quality Proxy Misses Real Damage

**Risk:** perplexity passes while instruction behavior degrades.

**Mitigation:** held-out PPL/KLD plus a small task-relevant behavioral suite and
qualitative examples chosen before candidate evaluation.

## R-07 Upstream Drift

**Risk:** `llama.cpp` or KleidiAI flags, dispatch behavior, or schemas change.

**Mitigation:** pin revisions, isolate adapters, source-rule version checks,
migration tests, and no unpinned `main` in headline evidence.

## R-08 Upstream Patch Is Too Invasive

**Risk:** tracing fork becomes unmaintainable and weakens reusable impact.

**Mitigation:** minimal opt-in hook, structured reason codes, focused tests,
separate patch series, and upstream-style review.

## R-09 AWS Cost Escape

**Risk:** stopped volumes, failed cleanup, long quality runs, or parallel agents
exceed the small budget.

**Mitigation:** one cloud experiment owner, TTL/watchdog, resource tags, no
parallel instances, spend ledger, terminate/delete verification.

## R-10 Licensing Or Gated Model Blocks Reproduction

**Risk:** judges cannot download the source model or redistribute artifacts.

**Mitigation:** select an ungated model with clear license; publish recipe and
hash even if model redistribution is restricted; record dataset licenses.

## R-11 UI Outruns Evidence

**Risk:** polished visuals imply precision that the trace does not possess.

**Mitigation:** UI consumes schemas, shows confidence/unknowns, links raw data,
and is built against truthful fixtures after feasibility.

## R-12 Project Scope Expands Again

**Risk:** adding frameworks, clouds, models, schedulers, or kernel generation
prevents finishing the central proof.

**Mitigation:** non-goals, ADR approval, one model/runtime/target for headline
evidence, and phase entry gates.

## Assumption Review Cadence

- Review R-01 through R-05 after every feasibility experiment.
- Review budget and licensing before provisioning.
- Review scope before accepting any new dependency or platform.
- Convert a disproven assumption into an ADR and revised requirement; never
  leave contradictory intent in conversation history.

