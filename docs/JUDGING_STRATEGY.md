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
- clean reproduction.

Do not attribute the whole BF16-to-INT4 transformation to KleidiAI.

## UX And Developer Experience: 15

The recurring workflow is a PR merge decision, not a one-time report. A
developer supplies one contract file and receives a GitHub Check, explanation,
report and deployable configuration.

Required proof:

- one-command reference run;
- stable failure reason codes;
- useful failed-state UX;
- documentation for replacing workload and adapter; and
- report provenance accessible without cloud access.

## Potential Impact: 20

Community artifacts are the contract schema, matched-control runner,
fail-closed claim ledger, quality interface, KleidiAI detector, GitHub Action,
report, deployment template and reference recipe.

The contribution is not another general benchmark. It makes Arm optimization
claims enforceable in a workflow maintainers already use.

## WOW: 25

The 90-second reveal is causal:

1. A PR claims Arm optimization.
2. KleidiAI is disabled; the check turns red and `kai_*` disappears.
3. KleidiAI is enabled; the check turns green and cloud capacity passes.
4. The exact accepted deployment becomes available.

The audience should understand the purpose within 15 seconds.

## Cloud AI Fit

The reference product evaluates a hosted CPU inference service under
concurrency, p95, throughput and memory constraints on Graviton4. It translates
Arm acceleration into deployable capacity rather than stopping at isolated
tokens per second.

## Score Target

The fully implemented concept is designed for approximately 38/40 technical,
14/15 DX, 18/20 impact and 23/25 WOW. These are planning targets, not claims or
guaranteed judge scores.

