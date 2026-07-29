# Claims, Requirements, And Evidence

This matrix is the acceptance layer between implementation and submission.
Status begins `unproven` and changes only when the referenced evidence exists.

| Claim ID | Intended claim | Requirements | Minimum evidence | Status |
|---|---|---|---|---|
| C-01 | KleidiScope observes actual KleidiAI execution rather than backend availability | INV-01, FR-02, FR-03 | enabled/disabled traces, source map, negative test | unproven |
| C-02 | Fallback explanations are source-grounded | FR-03, NFR-05 | pinned rules, source lines, rule tests | unproven |
| C-03 | Coverage metrics identify runtime-significant opportunities | FR-04, FR-05 | reconciled fixture and real weighted report | unproven |
| C-04 | Generated recipes are bounded and hardware-aware | FR-06, NFR-04 | deterministic policy tests, rationale per override | unproven |
| C-05 | Candidate models are reproducible | FR-07, FR-11, NFR-01 | recipe, command, hashes, clean rebuild | unproven |
| C-06 | Candidate preserves declared quality | INV-03, FR-08, FR-10 | held-out quality output and decision | unproven |
| C-07 | Candidate improves a declared Arm deployment objective | FR-08, FR-09, FR-10 | raw repeated benchmark and uncertainty | unproven |
| C-08 | Value exceeds generic upstream mixed quantization | INV-04, FR-09 | size/quality-matched target-BPW comparison | unproven |
| C-09 | Developer can reuse the tool on another model | FR-01-FR-13, NFR-06 | clean quickstart with second fixture/model smoke | unproven |
| C-10 | Report is an honest projection of evidence | INV-05, FR-12 | fixture provenance and browser tests | unproven |
| C-11 | CI can detect acceleration regressions | FR-13 | pass/fail/inconclusive workflow fixtures | unproven |
| C-12 | AWS experiment stayed within budget | NFR-09, FP-09 | spend ledger and cleanup verification | unproven |

## Evidence Acceptance Rules

- A code path is not evidence that it ran.
- A startup message is not sufficient evidence of per-operation acceleration.
- A generated command is not evidence that candidate creation succeeded.
- A dashboard is not evidence without raw inputs and regeneration.
- A single benchmark sample is not evidence of a stable performance change.
- A quality proxy is not evidence if its data leaked into candidate selection.
- A missing required baseline prevents C-07 and C-08 from passing.
- A claim may be `partial` when some properties pass, but partial claims cannot
  appear as headline submission facts.

## Status Vocabulary

- `unproven`: no accepted evidence.
- `partial`: some evidence exists but minimum bundle is incomplete.
- `inconclusive`: evidence is complete but cannot distinguish pass/fail.
- `refuted`: evidence contradicts the intended claim.
- `proven_for_scope`: accepted only for the named model/runtime/hardware scope.

No claim uses the bare status `proven`; experimental scope always matters.

## Submission Audit

Before recording the demo, extract every quantitative and qualitative claim
from the script and Devpost copy. Give each a claim ID or remove it. An
independent reviewer should attempt to refute each headline claim from raw
evidence.

