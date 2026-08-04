# Three-Minute Demo Script

Target duration: **2:40-2:50**. The spoken script is deliberately limited to
about 345 words so clicks and pauses fit inside three minutes.

## Prepare Before Recording

1. Follow [`LIVE_REQUEST_RUNBOOK.md`](LIVE_REQUEST_RUNBOOK.md) and leave both
   prepared endpoints warm.
2. Start SurgeDesk with `python3.12 scripts/serve_surgedesk.py --port 8765`.
3. Open `http://127.0.0.1:8765/surgedesk/#triage` at 100% zoom and select
   **Guard intervention**.
4. Prepare two terminal tabs without executing their commands:

   ```bash
   python3.12 scripts/demo_live_compare.py \
     --baseline-endpoint http://127.0.0.1:18001/infer \
     --optimized-endpoint http://127.0.0.1:18002/infer

   python3.12 scripts/demo_release_gate.py
   ```

5. Record the browser and terminal. Hide notifications and bookmarks.

## Exact Recording

### 0:00-0:15 - Hook

**Show:** SurgeDesk first viewport.

**Say:**

> SurgeDesk is a banking-support AI service on Graviton4. The same Phi-4 Mini
> INT4 deployment sustains at least twice the traffic when Arm KleidiAI is
> enabled. ArmProof makes that claim defensible: it rejected our more
> impressive 2.5-times number when the long test contradicted it.

### 0:15-0:35 - Live Illustration

**Do:** Run `demo_live_compare.py`. Let the enabled completion print first.

**Say:**

> This is one live illustrative request to two prepared endpoints, not the
> capacity benchmark. They use the same prompt, model and runtime; the
> KleidiAI control differs. Enabled finishes first. The sustained audit, not
> this single request, establishes the headline.

### 0:35-0:55 - User Workflow

**Do:** Return to SurgeDesk, click **Load model suggestion**, point to the two
queues, then click **Confirm route**.

**Say:**

> Phi-4 misroutes this missing card to security. The held-out guard repairs it
> to cards and payments. Across 770 unseen requests, operational accuracy is
> 86.75 percent, up 12.34 points. A human still confirms every route.

### 0:55-1:35 - Sustained Arm Result

**Do:** Open **2. Arm result**, click **Load verified experiment**, then point
to the blocked claim, proven lower bound and equal-load outcomes.

**Say:**

> Now I load immutable EXP-2026-009; I am not pretending to rerun hours of
> testing in seconds. On one c8g.4xlarge, the contract binds the model,
> runtime, workload, machine and 16 threads while its treatment overlay toggles
> KleidiAI. Five 500-second confirmations passed at 0.24 requests per second
> without KleidiAI and 0.56 with it. Baseline failed all five at 0.28, proving
> at least twice the sustainable capacity. The exact 2.5-times gate stayed
> blocked because 0.60 passed one window by 72 milliseconds. All 4,200 request
> outcomes remain in the audit.

### 1:35-2:08 - Prove Arm Caused It

**Do:** Open **3. Release proof** and point to the claim ledger and optimization
path.

**Say:**

> ArmProof verifies checksums, derives metrics from raw rows, binds treatment
> identities, then evaluates nine claims. INT4 reduced artifact size by 35.92
> percent and peak memory by 55.34 percent. Inside the identical INT4 runtime,
> KleidiAI produced 1.72 to 2.59-times direct speedup. Perf attributed 68.53
> percent of enabled cycles to its matrix callchain and zero in the control.
> Quality moved less than one point and schema validity remained 100 percent.

### 2:08-2:38 - Reusable Developer Artifact

**Do:** Run `demo_release_gate.py`. Point to `PASS`, `TAMPER`, `BLOCK`, then
show the `armproof init` command in the adoption panel or README.

**Say:**

> This is reusable software, not just our report. ArmProof ships a CLI, GitHub
> Action, schemas, fixed-SLO adapter and deployment recipe. One digest change
> blocks before policy evaluation. A new developer can scaffold the same
> fail-closed workflow with armproof init; the generated project refuses to
> pass until real evidence replaces its templates.

### 2:38-2:50 - Close

**Say:**

> SurgeDesk shows what Arm optimization changes for users. ArmProof proves why
> it changed. Same instance, at least twice the sustainable capacity, verified
> before merge.

Stop recording immediately.

## Recording Rules

- Call the live race an illustrative request, never capacity proof.
- Call the loaded audit sustained evidence, never a live benchmark.
- Do not call recorded requests live inference or ArmProof Arm-certified.
- Keep BF16-to-INT4 size and memory gains separate from KleidiAI gains.
- Keep the queue guard separate from the Arm optimization.
- Use no copyrighted music and publish the final video without sign-in.
