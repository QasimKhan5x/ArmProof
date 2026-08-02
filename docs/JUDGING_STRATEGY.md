# Judging Strategy

## Technological Implementation: 40

Show matched controls, fail-closed evidence, immutable identities, real
Graviton4 execution, PSS methodology, concurrent service testing and
positive/negative `kai_*` attribution.

Target evidence:

- 35.92% smaller INT4 artifacts;
- 55.34% lower peak PSS and 59.66% lower time-weighted PSS;
- 1.72x to 2.59x direct KleidiAI speedup;
- fixed-SLO capacity result;
- missing/swapped evidence rejection; and
- fresh-instance confirmation of tested boundaries.
- 86.75% held-out operational routing accuracy from a dependency-free guard.

Do not attribute the whole BF16-to-INT4 transformation to KleidiAI.

## UX And Developer Experience: 15

SurgeDesk first makes the value tangible: a support operator can confirm or
correct a route, watch the same queue under a measured surge and inspect why
the optimized deployment holds its SLO. The recurring developer workflow is a
PR merge decision. A developer supplies one contract file and receives a
GitHub Check, explanation, report and deployable configuration.

Required proof:

- one-command reference run;
- one continuous Triage -> Surge -> Release proof application path;
- stable failure reason codes;
- useful failed-state UX;
- documentation for replacing workload and adapter; and
- report provenance accessible without cloud access.
- a real endpoint mode that is enabled only when explicitly configured.

## Potential Impact: 20

Community artifacts are the contract schema, matched-control runner,
fail-closed claim ledger, quality interface, KleidiAI detector, GitHub Action,
report, deployment template and reference recipe.

The reference application and evidence-derived demo generator are also
reusable learning artifacts: they show how to turn raw fixed-SLO measurements
into an honest product demonstration without inventing live inference.

The contribution is not another general benchmark. It makes Arm optimization
claims enforceable in a workflow maintainers already use.

## WOW: 25

The 90-second reveal is operational and causal:

1. A stolen-card request reaches a human-confirmed support queue.
2. The two-stage route scores 86.75% held-out queue accuracy.
3. At identical demand, disabled shows three late customers while enabled
   shows zero on the same Graviton4 machine.
4. Sustainable mixed traffic rises from 0.20 to 0.60 requests/second.
5. ArmProof reveals enabled-only `kai_*` execution and releases the exact
   measured deployment through a reusable GitHub Action.

The audience should understand the application within 10 seconds and the Arm
optimization within 45 seconds. The report supports this reveal; it is not the
primary product screen.

## Cloud AI Fit

The reference product evaluates a hosted CPU inference service under
concurrency, p95, throughput and memory constraints on Graviton4. It translates
Arm acceleration into deployable capacity rather than stopping at isolated
tokens per second.

## Score Target

The fully implemented concept is designed for approximately 38/40 technical,
14/15 DX, 18/20 impact and 23/25 WOW. These are planning targets, not claims or
guaranteed judge scores.
