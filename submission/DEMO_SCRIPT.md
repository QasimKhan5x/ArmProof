# Three-Minute Demo Script

Target duration: **2:40-2:50**. Do not exceed 3:00. Every visible result must
be loaded or validated during the recording.

## Prepare Before Recording

1. Use a 1440x900 or 1440x960 browser window at 100% zoom.
2. Start the local app:

   ```bash
   python3.12 scripts/serve_surgedesk.py --port 8765
   ```

3. Open `http://127.0.0.1:8765/surgedesk/#triage`.
4. Select **Guard intervention** but do not load the suggestion yet.
5. Open a terminal beside the browser with this command already typed:

   ```bash
   armproof ci examples/armproof-reference/armproof.json
   ```

6. Close notifications, hide bookmarks and enable Do Not Disturb. Record only
   the browser and terminal. Do not use copyrighted music.

## Exact Recording

### 0:00-0:15 - Hook

**Show:** SurgeDesk triage, with the 86.75%, +12.34 pp and 100% score band in
the first viewport.

**Say:**

> This is SurgeDesk, a banking-support AI service on AWS Graviton4. We migrated
> Phi-4 Mini to INT4 ONNX Runtime GenAI and isolated Arm KleidiAI against the
> same model and runtime. The result is three times the sustainable mixed
> traffic on the same instance. ArmProof makes that claim reproducible and
> blocks it from regressing.

### 0:15-0:43 - Real Application And Honest Quality Boundary

**Do:** Click **Load model suggestion**. Point to **Phi-4 intent**, then
**LLM-mapped queue**, then **Guarded queue**. Click **Confirm route**.

**Say:**

> Here Phi-4 calls this a lost-card request and maps it to account security.
> The held-out queue guard sees that the card never arrived and repairs the
> operational route to cards and payments. Across 770 unseen requests this
> two-stage route reaches 86.75 percent, up 12.34 points. Every route remains
> human-confirmed; the app shows the model's limit instead of hiding it.

### 0:43-1:25 - The Arm Result, Loaded Honestly

**Do:** Click **2. Arm result**. Point briefly to `EXP-2026-004`, **141 files ·
SHA-256 verified**, and **Matched INT4 control**. Click **Load verified
experiment**. Point in this order: experiment strip, equal-load request rows,
p95 cells, 3.0x headline and the three traffic-mix rows.

**Say:**

> Now the optimization. I am loading accepted experiment EXP-2026-004, not
> pretending to run a benchmark in three seconds. This view is recomputed from
> raw events in a 141-file SHA-256 ledger. The matched deployment is one
> c8g.4xlarge, one Phi-4 Mini INT4 model, 16 threads and a 10-second p95 target;
> only KleidiAI changes. At equal load, disabled breaches the target three
> times at 12.66 seconds p95; enabled breaches none at 2.21. Five confirmations
> per boundary put mixed capacity at 0.20 versus 0.60 requests per second,
> with 2.5 to 3 times capacity across every traffic shape.

### 1:25-2:08 - Prove It Is Optimization On Arm

**Do:** Click **3. Release proof**. Point to the claim ledger. Scroll once to
the five-step optimization path and claim boundary.

**Say:**

> This is not a dashboard assertion. Phi-4 moved from BF16 to INT4, reducing
> the artifact by 35.92 percent, peak PSS by 55.34 percent and time-weighted
> PSS by 59.66 percent. Inside the identical INT4 deployment, KleidiAI delivers
> 1.72 to 2.59 times direct execution speedup, and kai callchains appear only
> in the enabled profile. Quality changed by less than one percentage point,
> schema validity stayed at 100 percent, and a fresh Graviton4 instance
> reproduced every capacity ratio exactly.

### 2:08-2:38 - Community Artifact

**Do:** Scroll to **The same decision runs in pull requests** and the
three-step adoption path. Switch to the terminal and press Enter on the
prepared command. Let the six passing claims print.

**Say:**

> ArmProof packages that method for other developers. One versioned contract
> connects quality, capacity, Arm execution, checksums and reproduction. A
> failure or unknown blocks CI. It ships as a zero-dependency Python CLI,
> GitHub Action, public schemas, matched-treatment runner, offline report and
> exact deployment manifest. Replace the adapter and workload to gate another
> Arm AI optimization.

### 2:38-2:50 - Close

**Do:** Return to the SurgeDesk proof header or keep the terminal output and
browser visible side by side.

**Say:**

> SurgeDesk shows what Arm optimization changes for users. ArmProof proves why
> it changed and lets the next Arm developer reuse the work. Same instance,
> three times the capacity, verified before merge.

Stop recording immediately.

## Recording Rules

- Click **Load verified experiment** during the video and call it an accepted
  evidence load, never a live benchmark.
- Do not call recorded requests live inference.
- Do not say Arm certified; say verified by ArmProof.
- Do not attribute BF16-to-INT4 size or memory gains to KleidiAI.
- Do not call the queue guard an Arm optimization.
- Keep the cursor moving only when it directs attention.
- Use hard cuts only for dead time; do not cut across an interaction in a way
  that suggests a different result.
- Upload publicly to YouTube or Vimeo and verify playback in a logged-out
  browser.
