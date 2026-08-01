# Agent Playbook

## Context Loading

Do not read every document. Start with `STATUS.md`, one work item and its
context paths. Keep loaded context below roughly 2,000 focused lines.

## Task Cycle

1. Confirm dependencies and authority.
2. Load the named files, related tests and one nearby pattern.
3. State the bounded implementation and verification plan.
4. Implement one vertical slice.
5. Run focused tests and context validation.
6. Store evidence and update work state.
7. Record any decision that changes public behavior.

## Conflicts

- Product spec versus old prose: product spec wins; clean the old prose.
- Planning versus raw evidence: raw evidence wins; narrow the claim.
- Documentation versus pinned source: verify source before implementation.
- Report versus claim ledger: claim ledger wins; reports do not decide.
- Work item versus repository state: repository state wins; repair status.

## Cloud Work

Before provisioning, load `docs/AWS_BUDGET.md`, the experiment contract and the
cloud work item. Confirm explicit approval, non-root credentials, tags, TTL,
cost cap and cleanup. Never improvise a second experiment in a paid session.

## Evidence Work

Observed facts, normalized facts and decisions are different layers. Preserve
the raw source for every normalized value. Do not hand-edit an accepted claim
result; rerun the validator from corrected evidence.

## UI Work

Develop against versioned fixture evidence after schemas freeze. The report
must show unavailable and failed states, not only the successful reference.
Use browser tests before calling the UI complete.

## Handoffs

At a handoff, `STATUS.md` must answer: what is established, what changed, what
failed, what is currently allowed, and what exact task comes next.

