# SurgeDesk Product And Demo Guide

SurgeDesk connects a practical support workflow to the deployment decision for
an Arm-optimized cloud model.

## Public Evidence Mode

```bash
python3.12 scripts/build_surgedesk_demo.py --verify
python3.12 scripts/serve_surgedesk.py --port 8765
```

Open <http://127.0.0.1:8765/surgedesk/>.

Recorded examples are read-only and labeled as stored model outputs. A support
agent chooses the final queue, including manual review, before a ticket enters
the audit trail. The public site exposes the checked-in release receipt and
native profiler results without an AWS dependency.

## Live Product Flow

The recording path connects two exact 16-thread Graviton4 treatment services:

```bash
python3.12 scripts/serve_surgedesk.py --port 8765 \
  --baseline-endpoint http://127.0.0.1:18001/infer \
  --optimized-endpoint http://127.0.0.1:18002/infer \
  --baseline-cores 0-15 \
  --optimized-cores 0-15
```

The state transition is:

1. One free-form customer message runs on the serving control and then on the
   candidate as a sequential shadow copy. The screen shows both fresh results
   without presenting one request as capacity proof.
2. The operator chooses the final support queue from the serving result.
3. ArmProof verifies the preregistered capacity, raw quality and Performix evidence.
4. The gateway probes both services and compares them with the audited deployment.
5. The route changes to the treatment only after the audit and deployment checks pass.
6. A different free-form message runs through the treatment and records the audit ID.
7. ArmProof generates a starter for another bounded classification service and
   runs its empty state through CI, which blocks until evidence exists.

The complete host setup, expected outputs and narration are in
[`submission/DEMO_SCRIPT.md`](../submission/DEMO_SCRIPT.md).

## Evidence Shown In The App

The capacity view reads the `EXP-2026-014` confirmation archive and shows the
two rates frozen in Git before the launch time recorded by the experiment. The
launch time is experiment metadata, not independent AWS attestation:

- control: five failures at 0.28 requests/s;
- treatment: five passes at 0.56 requests/s;
- window length: 500 seconds;
- raw request outcomes: 2,100; and
- released lower bound: at least 2.0x.

The proof view leads with:

- Arm Performix `kai_*` function-sample shares for both treatments;
- the observed Neoverse I8MM kernel family;
- Linux perf cycle attribution as a separate measurement;
- the release claims and thresholds; and
- the GitHub Action and adapter path under expandable technical detail.

The expandable detail also includes the exploratory direct-inference range
across four fixed input shapes and labels it separately from confirmed capacity.

The application page stays focused on support routing and deployment
activation. The detailed ledger and adoption material remain available for a
judge or developer who wants to inspect them.

## Identity Binding

The two live lanes must expose:

- the same content-derived model identity;
- the source-artifact SHA-256 declared by the release;
- the SHA-256 of the pinned runtime lock and verified runtime-wheel ledger;
- a `c8g.4xlarge` instance type read from AWS IMDSv2;
- ONNX Runtime GenAI at the pinned version;
- Arm64 architecture;
- 16 threads on the exact audited CPU set; and
- opposite values for `mlas.disable_kleidiai`.

Each inference response repeats the probed deployment data. Promotion compares
the model fingerprint, source artifact, runtime lock, verified wheel ledger,
IMDSv2 instance type, runtime, architecture, CPU placement and controls with the
saved-evidence validation. Every later optimized response is checked again. Drift blocks that
response, invalidates the release and returns the gateway to the control lane.

## Quality Boundary

The fine-grained BANKING77 intent accuracy is 46.49% for the optimized lane,
so SurgeDesk is an assistive workflow. The five-queue guard reached 86.75% on a
disjoint development holdout, and a person chooses the final queue. Selecting a
different queue removes the intent-mapped procedure unless that queue corresponds to
the known benchmark correction.

## Validate

```bash
make check
npm run test:logic
npm run test:ui
```

The suite covers raw evidence derivation, identity-bound gateway promotion,
human correction, browser history and focus, responsive layouts and the full
localhost HTTP transition from control to treatment.
