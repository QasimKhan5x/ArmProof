# Three-Minute Demo: Setup, Recording Script And Cleanup

Target duration: **2:50-2:58**. Speak conversationally and leave a short pause
after each result. The script is short enough to accommodate clicks within the
three-minute limit.

Run every command from the repository root unless a step says **Graviton**.
This is the only runbook needed to record the video.

## What Happens Live

The terminal sends one banking request concurrently to two warm services on the
same Graviton4 instance. Cores `0-7` run the KleidiAI-disabled control and cores
`8-15` run the KleidiAI-enabled treatment. This request makes the optimization
visible, while the capacity claim comes from the loaded `EXP-2026-009` audit:
twenty 500-second confirmation windows and 4,200 recorded requests.

## 1. Check The Local Demo

From the repository root, verify the comparison client and release-gate demo:

```bash
PYTHONPATH=src python3.12 -m unittest \
  tests.test_demo_live_compare tests.test_demo_release_gate -v
python3.12 scripts/demo_release_gate.py
```

Expected final output:

```text
OK
PASS    8/8 claims from 317 verified files
TAMPER  replaced one digest in a temporary copy of the primary ledger
BLOCK   release refused before policy evaluation: checksum mismatch
```

The unit test uses temporary local endpoints and validates orchestration only.

## 2. Prepare The Graviton Host

Use one Ubuntu 24.04 Arm64 `c8g.4xlarge` and record its public hostname and EC2
instance ID. The instance needs the repository, the pinned Arm64 runtime bundle
used by the experiments, and outbound access to Hugging Face. The runtime bundle
is not committed because it contains 45 MB of built wheels.

If both Graviton services are already prepared and warm, skip to step 4.

On the **recording machine**, set these values and upload the bundle:

```bash
export GRAVITON_HOST=ubuntu@YOUR_GRAVITON_HOST
export INSTANCE_ID=i-YOUR_INSTANCE_ID
export RUNTIME_BUNDLE=/absolute/path/to/runtime-checkpoints.tar.gz

test -f "$RUNTIME_BUNDLE"
ssh "$GRAVITON_HOST" 'uname -m'
scp "$RUNTIME_BUNDLE" "$GRAVITON_HOST:~/runtime-checkpoints.tar.gz"
```

Expected result: SSH prints `aarch64`, then `scp` reaches `100%` and returns to
the prompt.

On **Graviton**, install the pinned runtime and download the pinned model:

```bash
if [ -d ~/ArmProof/.git ]; then
  git -C ~/ArmProof pull --ff-only
else
  git clone https://github.com/QasimKhan5x/ArmProof.git ~/ArmProof
fi
cd ~/ArmProof

sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv curl
python3.12 -m venv ~/armproof-venv
~/armproof-venv/bin/pip install -q --upgrade pip
~/armproof-venv/bin/pip install -q -r ops/aws/cap-001/requirements.txt

mkdir -p ~/runtime-checkpoints ~/models
tar -xzf ~/runtime-checkpoints.tar.gz -C ~/runtime-checkpoints
(cd ~/runtime-checkpoints && sha256sum -c SHA256SUMS)
~/armproof-venv/bin/pip install -q --force-reinstall --no-deps \
  ~/runtime-checkpoints/onnxruntime-1.29.0-cp312-cp312-linux_aarch64.whl \
  ~/runtime-checkpoints/onnxruntime_genai-0.15.0.dev0-cp312-cp312-linux_aarch64.whl

~/armproof-venv/bin/hf download microsoft/Phi-4-mini-instruct-onnx \
  --revision fc04c8f93df696602fd9f300a30d1bf2e3081347 \
  --include 'cpu_and_mobile/cpu-int4-rtn-block-32-acc-level-4/*' \
  --local-dir ~/models/onnx-repo

PYTHONPATH=src ~/armproof-venv/bin/python scripts/prepare_phi4_variants.py \
  --source ~/models/onnx-repo/cpu_and_mobile/cpu-int4-rtn-block-32-acc-level-4 \
  --output-root ~/models/armproof-variants \
  --threads 8
```

Expected results:

- every line from `sha256sum` ends in `OK`;
- the Hugging Face command finishes with files under `~/models/onnx-repo`;
- variant preparation returns silently with exit code zero and creates
  `kleidiai-disabled` and `kleidiai-enabled`.

If `~/models/armproof-variants` already exists from a successful preparation,
skip the final command rather than overwriting it.

## 3. Start Both Graviton Services

Open two SSH terminals. These commands load the model and then remain silent
while serving requests; leave both terminals open.

In **Graviton terminal A**, start the disabled control:

```bash
cd ~/ArmProof
taskset -c 0-7 env OMP_NUM_THREADS=8 PYTHONPATH=src \
  ~/armproof-venv/bin/python -m armproof.reference.phi4 \
  --backend ort-int4 \
  --model ~/models/armproof-variants/kleidiai-disabled \
  --label ort-int4-kleidiai-disabled \
  --port 8001 --threads 8 --max-inflight 1
```

In **Graviton terminal B**, start the enabled treatment:

```bash
cd ~/ArmProof
taskset -c 8-15 env OMP_NUM_THREADS=8 PYTHONPATH=src \
  ~/armproof-venv/bin/python -m armproof.reference.phi4 \
  --backend ort-int4 \
  --model ~/models/armproof-variants/kleidiai-enabled \
  --label ort-int4-kleidiai-enabled \
  --port 8002 --threads 8 --max-inflight 1
```

## 4. Open The Tunnel And Verify Both Services

In a third terminal on the **recording machine**, open the SSH tunnel and leave
it running:

```bash
ssh -N \
  -L 18001:127.0.0.1:8001 \
  -L 18002:127.0.0.1:8002 \
  "$GRAVITON_HOST"
```

The tunnel prints nothing when healthy. In a fourth local terminal, verify the
two backend labels:

```bash
curl -s http://127.0.0.1:18001/health
echo
curl -s http://127.0.0.1:18002/health
echo
```

Expected output:

```json
{"ready":true,"backend":"ort-int4-kleidiai-disabled"}
{"ready":true,"backend":"ort-int4-kleidiai-enabled"}
```

## 5. Warm The Endpoints And Start SurgeDesk

Run the comparison once before recording:

```bash
python3.12 scripts/demo_live_compare.py \
  --baseline-endpoint http://127.0.0.1:18001/infer \
  --optimized-endpoint http://127.0.0.1:18002/infer
```

The times and ratio vary, and the two backend rows may appear in either order,
but both labels and the final capacity line must match:

```text
LIVE ILLUSTRATION - NOT CAPACITY EVIDENCE
Same request: i have not received my card
  KleidiAI enabled    <time> s  backend=ort-int4-kleidiai-enabled
  KleidiAI disabled   <time> s  backend=ort-int4-kleidiai-disabled
Illustrative request ratio: <ratio>x
Capacity claim: use EXP-2026-009 sustained evidence (>=2.0x).
```

Do not record if either label is missing or swapped. Start the local UI in a
fifth terminal:

```bash
python3.12 scripts/serve_surgedesk.py --port 8765
```

Expected output:

```text
SurgeDesk: http://127.0.0.1:8765/surgedesk/
Live inference: disabled
```

The disabled message is correct: the video uses the two live endpoints in the
terminal and SHA-256-locked evidence in the browser.

## 6. Stage The Recording

1. Open `http://127.0.0.1:8765/surgedesk/#triage` at 100% zoom.
2. Select **Guard intervention** and leave the page at the first viewport.
3. Clear the terminal used for the warm-up and paste, without running, the
   `demo_live_compare.py` command from step 5.
4. In another clear terminal, paste `python3.12 scripts/demo_release_gate.py`
   without running it.
5. Arrange the browser and terminal so switching between them takes one click.
6. Hide notifications and bookmarks, then start recording.

## 7. Record The Video

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

## 8. Stop Services And Terminate AWS

After recording:

1. Press `Ctrl-C` in both Graviton service terminals, the SSH tunnel terminal
   and the local SurgeDesk terminal.
2. Terminate the instance from the recording machine:

   ```bash
   aws ec2 terminate-instances \
     --region us-east-1 \
     --instance-ids "$INSTANCE_ID" \
     --query 'TerminatingInstances[0].[InstanceId,CurrentState.Name]' \
     --output text

   aws ec2 wait instance-terminated \
     --region us-east-1 \
     --instance-ids "$INSTANCE_ID"
   ```

   Expected first output:

   ```text
   i-YOUR_INSTANCE_ID    shutting-down
   ```

3. Confirm that no running ArmProof instance remains:

   ```bash
   aws ec2 describe-instances \
     --region us-east-1 \
     --filters \
       'Name=tag:Project,Values=ArmProof' \
       'Name=instance-state-name,Values=pending,running,stopping,stopped' \
     --query 'Reservations[].Instances[].[InstanceId,State.Name]' \
     --output text
   ```

   Expected output: empty.

If either live endpoint returns the wrong label, fails, or produces an ambiguous
result, fix the endpoint setup before recording. Never substitute synthetic
terminal output.
