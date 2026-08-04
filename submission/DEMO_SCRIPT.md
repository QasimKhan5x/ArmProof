# Three-Minute Demo Script

Target duration: **2:40-2:50**. Speak conversationally and leave a short pause
after each result. The script is short enough to accommodate clicks within the
three-minute limit.

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
> INT4 model handles at least twice the traffic with Arm KleidiAI. First, I will
> show the support workflow. Then we will open the measurements behind it.

### 0:15-0:35 - Live Illustration

**Do:** Run `demo_live_compare.py`. Let the enabled completion print first.

**Say:**

> I am sending the same customer message to two live endpoints. They use the
> same model and runtime settings; only KleidiAI changes. The optimized endpoint
> completes first. Later tests show whether this advantage survives sustained
> traffic.

### 0:35-0:55 - User Workflow

**Do:** Return to SurgeDesk, click **Load model suggestion**, point to the two
queues, then click **Confirm route**.

**Say:**

> This customer has lost a card. The model initially sends the case to the
> security queue. The routing guard corrects it to cards and payments. Across
> 770 unseen messages, the guard raises accuracy by 12.34 points. The support
> agent reviews the suggestion and confirms it.

### 0:55-1:42 - Sustained Arm Result

**Do:** Open **2. Arm result**, click **Load verified experiment**, then point
to the blocked claim, proven lower bound and equal-load outcomes.

**Say:**

> This test asks how many banking messages one server can process while keeping
> p95 response time under ten seconds and returning no errors. At each traffic
> rate, we ran five 500-second trials. Without KleidiAI, 0.24 requests per second
> passed every trial, while 0.28 failed every trial. With KleidiAI, 0.56 passed
> all five. Since 0.56 is twice 0.28, the optimized capacity is at least twice
> the baseline capacity.
>
> Shorter tests had suggested 2.5 times. ArmProof reprocessed all 4,200 request
> records and required all five trials to agree. At 0.60, one trial slipped
> under the ten-second limit by 72 milliseconds. The exact capacity boundary
> was therefore not reproducible, so ArmProof rejected 2.5 times and released
> only the two-times claim.

### 1:42-2:14 - Prove Arm Caused It

**Do:** Open **3. Release proof**. Point first to **Core causal experiment**,
then the claim ledger and optimization path.

**Say:**

> Performix shows where the gain came from. With KleidiAI disabled, none of its
> samples landed in KleidiAI code. With it enabled, 67.02 percent landed in the
> Neoverse I8MM matrix kernel. Linux perf measured 68.53 percent. ArmProof checks
> both profiles during CI. INT4 also cut model size by 35.92 percent and peak
> memory by 55.34 percent, while quality stayed within one point.

### 2:14-2:43 - Reusable Developer Artifact

**Do:** Run `demo_release_gate.py`. Point to `PASS`, `TAMPER`, `BLOCK`, then
show the `armproof init` command in the adoption panel or README.

**Say:**

> ArmProof first validates eight release claims across 317 files: request logs,
> summaries and profiler exports. Now I replace one SHA-256 fingerprint in the
> experiment ledger. The fingerprint no longer matches its evidence file, so
> ArmProof cannot prove it is evaluating the recorded experiment and blocks the
> release. Developers get the same check through the CLI or GitHub Action, and
> armproof init adds it to another project.

### 2:43-2:55 - Close

**Say:**

> Twice the AI traffic, on the same Graviton server, with evidence checked
> before release.

Stop recording immediately.

## Recording Rules

- Call the live race an illustrative request, never capacity proof.
- Call the loaded audit sustained evidence, never a live benchmark.
- Do not call recorded requests live inference or ArmProof Arm-certified.
- Keep BF16-to-INT4 size and memory gains separate from KleidiAI gains.
- Keep the queue guard separate from the Arm optimization.
- Use no copyrighted music and publish the final video without sign-in.
