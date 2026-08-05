# Capacity Validation

The public service claim comes from the preregistered EXP-2026-014 confirmation.

## Service Rule

A window passes when all three conditions hold:

- 95th-percentile response time is at or below 10 seconds;
- no request errors occur; and
- accepted request rate reaches at least 95% of the offered rate.

The open-loop client schedules requests independently of response completion.
The release verifier measures from `scheduled_ns` through `finished_ns`, so
client dispatch delay is included. A completion after the 500-second window
plus the ten-second SLO drain is counted as a failed request. These rules are
frozen in [`EXP-2026-014-analysis.json`](../ops/experiments/EXP-2026-014-analysis.json).

## Frozen Confirmation

Before the instance launched, [`EXP-2026-014`](../ops/experiments/EXP-2026-014.json)
and its [`protocol`](../ops/aws/sustained-006/protocol.json) fixed one possible
success outcome:

| Lane | Offered rate | Independent windows | Required outcome |
|---|---:|---:|---|
| KleidiAI disabled | 0.28 requests/s | 5 x 500 seconds | all fail |
| KleidiAI enabled | 0.56 requests/s | 5 x 500 seconds | all pass |

The two treatments use the same source model, INT4 files, runtime, API, 16
threads, workload and server. Each window starts a fresh service process and is
warmed before measurement. Treatment order alternates by repetition.

The ten windows contain 2,100 raw request outcomes. A control pass, treatment
failure, missing row, cadence mismatch, response-identity mismatch, quality
breach or treatment-config mismatch rejects the release. The verifier does not
search for replacement rates.

## Derivation

The conservative capacity lower bound is:

```text
treatment passing rate / control failing rate
0.56 / 0.28 = at least 2.0x
```

Because the control fails at 0.28 requests/s, its sustainable rate is below
0.28 under this response-time rule. Because the treatment passes at 0.56, its
sustainable rate is at least 0.56. The ratio is therefore a lower bound rather
than an estimate of either lane's exact maximum.

[`confirmed_audit.py`](../src/armproof/evidence/confirmed_audit.py) reopens the
archive, requires its experiment and protocol to equal the committed files,
forces every lane to its frozen rate, reconstructs every request summary from
timestamps and responses, and evaluates the release contract.

## Discovery History

EXP-2026-004 through EXP-2026-009 explored candidate grids, process isolation
and longer windows. EXP-2026-009 found the standard service passing five of five
windows at 0.24 requests/s and failing five of five at 0.28. The optimized
service passed five of five at 0.56, while its 0.60 probe was mixed. The final
experiment therefore froze only the 0.28 standard failure and 0.56 optimized
pass; it did not claim an exact optimized upper boundary. Discovery evidence
remains visible under `ops/evidence/`, but it cannot approve the current release.

EXP-2026-012 then tested those same two rates and matched the intended capacity
outcomes, but its successful responses omitted the source-artifact hash required
by its analysis lock. ArmProof rejected that archive. EXP-2026-014 changes no
performance parameter; it repeats the same test with the complete response
identity and is the only capacity archive consumed by the release.
