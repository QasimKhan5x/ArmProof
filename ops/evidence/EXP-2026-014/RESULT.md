# EXP-2026-014 Result: Accepted

The preregistered Graviton4 confirmation passed without changing its rates,
workload, SLO, runtime, model, or acceptance rules after launch.

- KleidiAI-disabled control at `0.28 requests/s`: five of five 500-second
  windows failed the 10-second p95 SLO.
- KleidiAI-enabled treatment at `0.56 requests/s`: five of five 500-second
  windows passed the same SLO with zero request errors.
- The ten windows contain 2,100 raw scheduled-request records. Their outcomes
  are re-derived from timestamps rather than accepted from the collector
  summary.
- The matched quality evidence contains 1,540 raw model outputs. Accuracy
  changed by -0.39 percentage points, macro F1 by -0.67 points, and schema
  validity remained 100%.
- Every successful capacity response includes the frozen source-model,
  runtime, Arm64, 16-thread, affinity, and KleidiAI-control identity.
- The final confirmation therefore establishes the preregistered lower bound
  `0.56 / 0.28 = at least 2.0x` sustainable capacity on the same instance.

The preregistration Git object
[`ab22cc0`](https://github.com/QasimKhan5x/ArmProof/commit/ab22cc055881c5e8bae35dd6e4d919f0b407971e)
contains the exact plan and its time predates the recorded instance launch and
measurement start. The exact plan bytes are also embedded in both the prelaunch
project bundle and the returned evidence archive. ArmProof verifies those
hashes and recorded timestamps before evaluating the ten release claims; it
does not independently attest GitHub publication time or AWS launch time.

The separate accepted EXP-2026-013 native Performix profiles are bound to the
same source model, runtime, workload, Arm machine shape, and KleidiAI control.
They report zero `kai_*` function samples in the control and 245,876 of 365,062
samples (67.35%) in the treatment, including the Neoverse I8MM matrix kernel.

## Audit artifacts

- `evidence.tar.gz`: SHA-256 `c4f94870eece68081c54411eedc24e17ae3b6d541afb94daee7ed86577a1bb06`
- `project.tar.gz`: SHA-256 `bde113a3ea0911fc761895fe68c043f3f81ed5cc5a8e8bf9d86b8a6c73112fb9`
- Preregistration plan: SHA-256 `534933500ac1c8af473d0b649be30bcae285743e616513dbdeeae0cce0935e84`
- Accepted session cost: `$1.0503`
- Conservative cumulative project estimate: `$13.4872`
- AWS cleanup: complete; instance terminated; post-run inventory empty
