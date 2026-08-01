# SurgeDesk Demo Guide

## Purpose

SurgeDesk turns the accepted Phi-4 Mini Graviton experiment into a practical
support-operations workflow. It is deliberately offline and deterministic so
the judge sees the measured result even without AWS access.

## Run

```bash
python3.12 scripts/build_surgedesk_demo.py --verify
python3.12 -m http.server 8765 --bind 127.0.0.1
```

Open `http://127.0.0.1:8765/surgedesk/`.

## Workflow

1. **Triage:** choose a real BANKING77 request, load its recorded Phi-4 Mini
   INT4 prediction, then confirm or correct the proposed queue. The audit trail
   displays the final human decision and procedure.
2. **Surge replay:** replay raw mixed-traffic confirmation events. The disabled
   control breaches the 10-second p95 objective; the enabled treatment passes.
   The sustainable mixed boundary is 0.20 versus 0.60 requests/second.
3. **Release proof:** inspect the claim ledger, executed Arm path, quality
   boundary, exact deployment and reusable GitHub Action.

## Evidence Provenance

`scripts/build_surgedesk_demo.py` calls
`src/armproof/demo/surgedesk.py`, which joins:

- accepted BANKING77 quality inputs and recorded Phi-4 outputs;
- raw `rep-1-fail.jsonl` and `rep-1-pass.jsonl` request samples;
- accepted short, long and mixed capacity boundaries;
- quality, artifact size, PSS and direct KleidiAI summaries; and
- clean-machine reproduction plus enabled/disabled callchain evidence.

The generated `surgedesk/data.json` is checked into the repository for an
offline demo. `--verify` byte-compares it with a fresh derivation and fails CI
if it drifts.

## Integrity Boundary

- The sample picker replays recorded model outputs; it is not live inference.
- Editing a message disables lookup and produces an explicit error.
- The optimizer preserved quality within tolerance, but absolute accuracy is
  46.49% across 77 classes. The app therefore requires human confirmation.
- All claims are scoped to the pinned Phi-4 Mini workload, ONNX Runtime GenAI
  INT4 runtime and AWS Graviton4 `c8g.4xlarge`.

## Validate

```bash
make check
npm run test:logic
npm run test:ui
```

The browser suite covers confirmation, correction, edited-text rejection, raw
replay convergence, proof visibility, console errors and 320-pixel overflow.
