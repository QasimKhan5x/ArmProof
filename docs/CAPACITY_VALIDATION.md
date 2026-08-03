# Fixed-SLO Capacity Validation

## Status

Short-window gate completed by `EXP-2026-004` on 2026-07-31. Public sustained
claim superseded by long-window audit `EXP-2026-009` on 2026-08-03.

## Question

Does the existing KleidiAI acceleration produce materially higher sustainable
cloud-service throughput at the same p95 SLO?

## Treatments

- Phi-4 Mini INT4 ONNX Runtime GenAI with KleidiAI disabled.
- Identical model, runtime, service, thread settings and workload with
  KleidiAI enabled.

PyTorch BF16 is retained for whole-deployment memory, size and quality context,
not the Arm causal throughput comparison.

## Workload

- Public licensed task data.
- Frozen short, long and mixed prompt mixes.
- Deterministic generation and output parser.
- At least 500 quality requests; 1,000 preferred.
- At least five capacity runs per treatment and mix.

## Primary Gate

- Minimum: 1.5x sustainable accepted throughput at the same p95 SLO in at
  least two of three traffic mixes.
- Preferred headline: 1.7x.
- Lower 95% confidence bound above 1.15x.
- No quality difference between the enabled and disabled identical-runtime
  treatments.
- `kai_*` present only when enabled.

## Secondary Gates

- Non-profiler ArmProof overhead below 5%.
- No unexplained treatment configuration difference.
- Complete raw bundle and terminated AWS resources.
- Repetition validity and error rates satisfy the benchmark protocol.

## Short-Window Outcome

- `PASS`: 3.0x short, 2.5x long and 3.0x mixed fixed-SLO capacity.
- Quality: -0.390 pp accuracy and -0.673 pp macro F1; 100% schema validity.
- Attribution: `kai_*` observed only in the enabled profile.
- Repetitions: five passing and five failing boundary confirmations for every
  treatment and traffic mix.
- Integrity: all 141 guest checksums verify after evidence relocation.
- Cleanup: no paid resources remain; session cost USD 0.7057.

`EXP-2026-003` remains inconclusive because its nominal and actual offered
rates differed. Its raw results were not promoted into the accepted claim.

## Decisive Sustained Outcome

`EXP-2026-009` used isolated processes and five 500-second confirmations at
every frozen pass/fail boundary. Disabled 0.24 r/s and enabled 0.56 r/s passed
all five; disabled 0.28 r/s failed all five. The defensible public result is
therefore at least 2.0x sustainable capacity with a 2.33x tested pass-point
ratio. The preregistered exact 2.0x-2.5x bracket was rejected because enabled
0.60 r/s passed one of five windows. No exact maximum-capacity estimate is made.

## Cost Boundary

One `c8g.4xlarge`, expected 60-90 minutes, hard stop at two hours, with a USD 2
compute target and the repository-wide cloud ceiling enforced.
