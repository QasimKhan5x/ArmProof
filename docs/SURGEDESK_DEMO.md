# SurgeDesk Demo Guide

## Purpose

SurgeDesk turns the accepted Phi-4 Mini Graviton experiment into a practical
support-operations workflow. Recorded mode is deterministic so the judge sees
the measured result without AWS access; the same gateway can also connect to a
real Graviton endpoint for the opening request.

## Run

```bash
python3.12 scripts/build_surgedesk_demo.py --verify
python3.12 scripts/serve_surgedesk.py --port 8765
```

Open `http://127.0.0.1:8765/surgedesk/`.

## Workflow

1. **Triage:** inspect the held-out `86.75%` queue result, load a recorded
   Phi-4 intent, observe the queue guard rescue or error, then confirm or
   correct the proposed route.
2. **Surge replay:** replay the same eight requests at `0.267 requests/second`.
   Disabled records three SLO breaches and `12.66s` p95; enabled records none
   and `2.21s` p95. The separate five-run boundary is 0.20 versus 0.60.
3. **Release proof:** inspect the claim ledger, executed Arm path, quality
   boundary, exact deployment and reusable GitHub Action.

## Evidence Provenance

`scripts/build_surgedesk_demo.py` calls
`src/armproof/demo/surgedesk.py`, which joins:

- accepted BANKING77 quality inputs and recorded Phi-4 outputs;
- equal-load discovery samples plus five-run confirmed capacity boundaries;
- a queue guard trained on 2,310 disjoint examples and evaluated on the frozen
  770-case quality set;
- accepted short, long and mixed capacity boundaries;
- quality, artifact size, PSS and direct KleidiAI summaries; and
- clean-machine reproduction plus enabled/disabled callchain evidence.

The generated `surgedesk/data.json` is checked into the repository for an
offline demo. `--verify` byte-compares it with a fresh derivation and fails CI
if it drifts.

## Integrity Boundary

- The sample picker replays recorded model outputs and is labeled accordingly.
- Editing a message disables lookup and produces an explicit error.
- Operational five-destination accuracy is 86.75%; fine-grained 77-intent accuracy is
  46.49%. The app therefore requires human confirmation.
- All claims are scoped to the pinned Phi-4 Mini workload, ONNX Runtime GenAI
  INT4 runtime and AWS Graviton4 `c8g.4xlarge`.

## Live Graviton Mode

Forward the measured service to localhost, then run:

```bash
SURGEDESK_INFERENCE_ENDPOINT=http://127.0.0.1:8000/infer \
  python3.12 scripts/serve_surgedesk.py --port 8765
```

The **Live Graviton endpoint** control becomes available. The gateway accepts
only bounded text, builds the frozen intent prompt, calls the trusted endpoint
with a 60-second timeout and applies the same local queue guard. Without that
environment variable, live mode remains disabled rather than faking output.

## Validate

```bash
make check
npm run test:logic
npm run test:ui
```

The browser suite covers confirmation, correction, edited-text rejection, raw
replay convergence, proof visibility, console errors and 320-pixel overflow.
