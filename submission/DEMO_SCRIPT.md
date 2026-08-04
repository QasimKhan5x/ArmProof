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

> SurgeDesk runs a Phi-4 Mini INT4 banking-support service on Graviton4.
> Enabling Arm KleidiAI lets the same server handle at least twice the traffic,
> and I will show the workflow, benchmark and release evidence behind that
> result.

### 0:15-0:35 - Live Illustration

**Do:** Run `demo_live_compare.py`. Let the enabled completion print first.

**Say:**

> Here, the same customer message goes to two live endpoints with identical
> model and runtime settings. KleidiAI is the only change, and the optimized
> endpoint finishes first; the sustained benchmark will show whether that lead
> holds under traffic.

### 0:35-0:55 - User Workflow

**Do:** Return to SurgeDesk, click **Load model suggestion**, point to the two
queues, then click **Confirm route**.

**Say:**

> The model initially sends this missing-card case to security, but the routing
> guard corrects it to cards and payments. Across 770 unseen messages, the guard
> raises accuracy by 12.34 points before the agent reviews and confirms the
> suggestion.

### 0:55-1:42 - Sustained Arm Result

**Do:** Open **2. Arm result**, click **Load verified experiment**, then point
to the blocked claim, proven lower bound and equal-load outcomes.

**Say:**

> The benchmark measures how many banking messages one server can process while
> keeping p95 response time under ten seconds with no errors. At each traffic
> rate, we ran five 500-second trials. The baseline passed all five at 0.24
> requests per second but failed all five at 0.28, while the optimized service
> passed all five at 0.56. Since the baseline cannot sustain 0.28 while the
> optimized service sustains 0.56, the capacity gain is at least two times.
>
> Short tests had suggested 2.5 times, but ArmProof reprocessed all 4,200 request
> records and required every trial to agree. At 0.60, one optimized trial passed
> by 72 milliseconds, so that boundary was not reproducible; ArmProof rejected
> the exact 2.5-times estimate and published the defensible two-times result.

### 1:42-2:20 - Prove Arm Caused It

**Do:** Open **3. Release proof**. Point first to **Core causal experiment**,
then the claim ledger and optimization path.

**Say:**

> To check that the gain came from Arm-optimized execution, Performix profiled
> otherwise identical enabled and disabled runs. It found zero KleidiAI samples
> when disabled, compared with 67.02 percent in the Neoverse I8MM matrix kernel
> when enabled. Linux perf independently attributed 68.53 percent of CPU cycles
> to the same call chain, and ArmProof validates both profiles during CI.
> Separately, INT4 reduced model size by 35.92 percent and peak memory by 55.34
> percent while accuracy remained within one point.

### 2:20-2:46 - Reusable Developer Artifact

**Do:** Run `demo_release_gate.py`. Point to `PASS`, `TAMPER`, `BLOCK`, then
show the `armproof init` command in the adoption panel or README.

**Say:**

> ArmProof first validates eight claims from 317 request logs, summaries and
> profiler files. I then replace one SHA-256 fingerprint in the experiment
> ledger. Because it no longer matches the recorded evidence, ArmProof blocks
> the release instead of trusting the metrics. Developers can add the same check
> to another Arm AI project through the CLI, GitHub Action and armproof init.

### 2:46-2:56 - Close

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
