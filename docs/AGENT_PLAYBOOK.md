# Long-Horizon Agent Playbook

This repository is designed for agents working across many context windows.
Conversation history is convenient but non-authoritative.

## Context Layers

1. `AGENTS.md`: short persistent rules and routing map.
2. `STATUS.md`: current verified state and next action.
3. `ops/work-items.json`: machine-readable dependency and verification state.
4. Relevant spec/architecture sections selected by the work item.
5. Nearby source/tests and current command output.
6. Conversation history only for unresolved nuance.

Avoid loading the entire project corpus for a narrow task.

## Standard Session Loop

### Orient

- Confirm repository path and branch.
- Read status, work item, recent commits, and working-tree changes.
- Identify user-authored changes and preserve them.
- Run the documented health check.

### Select

- Choose one highest-priority unblocked work item.
- Confirm its dependencies are actually evidenced, not merely marked complete.
- Load only its context files and related source/tests.

### Predict

Before a non-trivial change, record:

- what observable behavior should change;
- what should remain unchanged;
- verification command and expected evidence;
- risks and rollback boundary.

For experiments, create a preregistration record before seeing results.

### Implement Incrementally

- Add or update a failing test/fixture first when behavior is testable.
- Make the smallest coherent change.
- Re-run focused verification.
- Expand verification according to blast radius.
- Do not combine unrelated refactoring.

### Prove

- Execute the work item's verification.
- Inspect outputs, not only exit status.
- Store evidence paths.
- Try at least one negative or failure case.
- For consequential claims, use a fresh-context reviewer to attempt refutation.

### Persist

- Update the work item status and evidence references.
- Append experiment records; never rewrite an unfavorable run.
- Update `STATUS.md` with exact current state and one next action.
- Add an ADR if architecture, scope, claims, or constraints changed.
- Leave commands and the working tree understandable to the next agent.

## Work Item State Machine

```text
pending -> in_progress -> verifying -> completed
                  |           |
                  v           v
                blocked     failed
```

- `completed` requires the specified evidence.
- `blocked` names an external dependency and attempted alternatives.
- `failed` means the attempted implementation/experiment did not satisfy its
  gate; failure evidence remains useful.
- Reopening a completed item requires a reason and invalidated evidence link.

## Experiment Loop

```text
hypothesis -> preregistration -> execution -> raw evidence
     -> analysis -> accept/reject/inconclusive -> next hypothesis
```

Do not let analysis mutate the original hypothesis or thresholds. Follow-up
exploration receives a new experiment ID.

## Compaction Handoff

Before anticipated compaction, ensure `STATUS.md` contains:

- what is complete and how it was verified;
- what is currently running or partially edited;
- exact failing command/output summary;
- decisions made and alternatives rejected;
- paid resources still active;
- the single next action.

Never store secrets or huge logs in `STATUS.md`; link to local evidence.

## Parallel Agent Rules

- Decompose by disjoint write ownership.
- Freeze shared schemas before parallel implementation.
- Give each worker explicit inputs, output paths, tests, and non-goals.
- One integrator owns shared state and cloud experiments.
- Review returned patches before marking work complete.
- Do not have multiple agents provision AWS independently.
- Use independent agents for adversarial verification after evidence exists,
  not for duplicating speculative implementation.

## Anti-Drift Checks

At phase boundaries ask:

- Are we still solving dispatch visibility plus Arm-aware optimization?
- Did a new feature enter without a requirement and ADR?
- Does the headline depend on an unverified inference?
- Are existing upstream capabilities represented as baselines?
- Can a judge reproduce the claim without private context?
- Is the next phase justified by the prior gate?

## Definition Of Done

Code generation is not completion. A work item is done only when:

- acceptance behavior exists;
- negative/failure behavior exists;
- tests and required real evidence pass;
- docs and schemas agree;
- cost/security/license constraints are satisfied;
- status and traceability are updated;
- no required process remains running.

