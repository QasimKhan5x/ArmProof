# Three-Minute Demo And Recording Runbook

This document contains the complete setup, preflight, recording sequence and
cleanup. The browser begins with an empty live request. During the recording,
you enter two customer messages, route the first through the control deployment,
activate the audited Arm treatment, and route the second through that treatment.

Target length: **2:35 to 2:50**. Keep ten seconds of margin for live inference.

Use the narration as a rehearsal guide and speak in your normal words while
recording. The screen actions and factual boundaries are the parts that must
remain exact.

## 1. Check The Repository

Run on the recording Mac from the repository root:

```bash
make check
npm run test:logic
npm run test:ui
PYTHONPATH=src python3.12 -m armproof.cli ci \
  examples/armproof-reference/armproof.json
```

Expected result: the Python, logic and browser suites pass, and ArmProof exits
with code `0` after approving every required claim in the confirmed contract.

## 2. Prepare A Graviton4 Host

Use Ubuntu 24.04 Arm64 on one AWS `c8g.4xlarge`. On the Mac, set these values:

This owner-only path requires authenticated AWS credentials, `c8g.4xlarge`
quota in the selected region, an SSH key, port-22 access from the recording
Mac, and the pinned runtime bundle produced during project setup. Judges can
verify the checked-in evidence without AWS access or this bundle.

```bash
export GRAVITON_HOST=ubuntu@YOUR_PUBLIC_DNS_NAME
export INSTANCE_ID=i-YOUR_INSTANCE_ID
export RUNTIME_BUNDLE="$(cd .. && pwd)/result-first-bakeoff/evidence/checkpoints/runtime-checkpoints.tar.gz"

test -f "$RUNTIME_BUNDLE"
ssh "$GRAVITON_HOST" 'uname -m'
```

Expected output from `uname -m`: `aarch64`.

Upload the pinned runtime and clone the project:

```bash
scp "$RUNTIME_BUNDLE" "$GRAVITON_HOST:~/runtime-checkpoints.tar.gz"
ssh "$GRAVITON_HOST" '
  if [ -d ~/ArmProof/.git ]; then
    git -C ~/ArmProof pull --ff-only
  else
    git clone https://github.com/QasimKhan5x/ArmProof.git ~/ArmProof
  fi
  ~/ArmProof/scripts/prepare_live_demo_host.sh
'
```

The final line must begin with `READY` and show the source-model SHA-256 plus
`threads=16`. The setup script compares the downloaded model fingerprint with
the artifact identity in the release before creating either treatment.

## 3. Start The Two Exact Treatment Configurations

Open two terminals on the Mac and leave these commands running.

Terminal A:

```bash
ssh -t "$GRAVITON_HOST" '~/ArmProof/scripts/run_live_demo_lane.sh baseline'
```

Terminal B:

```bash
ssh -t "$GRAVITON_HOST" '~/ArmProof/scripts/run_live_demo_lane.sh optimized'
```

Both services use all 16 Graviton4 cores because the long capacity experiment
also used 16 threads. The gateway sends ordinary product traffic to one active
lane at a time.

Open a third terminal for the tunnel:

```bash
ssh -N \
  -L 18001:127.0.0.1:8001 \
  -L 18002:127.0.0.1:8002 \
  "$GRAVITON_HOST"
```

## 4. Preflight The Live Endpoints

From the repository root on the Mac:

```bash
python3.12 scripts/demo_live_compare.py \
  --baseline-endpoint http://127.0.0.1:18001/infer \
  --optimized-endpoint http://127.0.0.1:18002/infer
```

Expected ending:

```text
READY matched endpoint identities verified; request latency is a warm-up observation.
```

Start a fresh gateway after the preflight. A new process resets the active lane
to the control and clears all release state:

```bash
python3.12 scripts/serve_surgedesk.py \
  --port 8765 \
  --baseline-endpoint http://127.0.0.1:18001/infer \
  --optimized-endpoint http://127.0.0.1:18002/infer \
  --baseline-cores 0-15 \
  --optimized-cores 0-15
```

Open <http://127.0.0.1:8765/surgedesk/#triage>. Select **Live Arm64
inference**, confirm that the message box is empty, then return focus to the
browser address bar. Do not enter either recording message during setup.

## 5. Record The Video

Record at 1440×900 or 1920×1080 with browser zoom at 100%. Hide bookmarks,
notifications and unrelated tabs. Keep terminals and AWS consoles outside the
capture. The sequence below takes about **2:45** at a natural speaking pace.

Use this customer message both times:

```text
My card was stolen while I am travelling. Freeze it and help me replace it.
```

### 0:00-0:32 - Handle A Real Request

Start on the empty live request form. Type the message and click **Run live
route**. Point to the fresh request ID, timestamp, `aarch64 · 16 threads`, and
`mlas.disable_kleidiai=1` receipt. Choose **Account security**, then click
**Route ticket**.

> This customer message just ran through Phi-4 on our 16-core Graviton4
> service. SurgeDesk identified the issue, found the card-security procedure,
> and left the final queue to the support agent. The receipt shows the real
> Arm64 request and the standard KleidiAI-off configuration that served it.

### 0:32-1:18 - Establish The Operational Problem

Click **Review measured upgrade**, **Verify measured experiment**, then **Open confirmed result**. The local audit usually completes in about a second; point
to its five completed stages, 2,100 request outcomes and 1,540 model outputs.
Scroll to **What the support queue experienced**, then the capacity equation.

> During sustained traffic, every standard-service trial missed our ten-second
> target: p95 response time reached about a minute at 0.28 requests per second.
> With only KleidiAI changed, all five optimized trials stayed near 3.35 seconds
> while accepting 0.56 requests per second. These frozen rates establish the
> conservative result shown here: at least twice the sustainable capacity.

### 1:18-1:50 - Show Why The Gain Is Arm-Specific

Scroll to **Evidence that KleidiAI ran**, then click **Review and activate the optimized service** and **Activate verified optimized service**. Point to the
model fingerprint, runtime, Arm shape, and `1 → 0` control change.

> Both lanes use the same INT4 model, runtime, workload, server and 16 threads.
> Performix found no KleidiAI samples in the control and 67.35 percent in the
> treatment, including the Neoverse I8MM kernel. The live identities match the
> measured release, so SurgeDesk can switch lanes.

### 1:50-2:17 - Close The Loop With The Same Request

Click **Route the next live request**, paste the same customer message, and
click **Run live route**. Point to the new request ID, timestamp and
`mlas.disable_kleidiai=0`. Choose **Account security**, click **Route ticket**,
and show both entries in the ticket history.

> The same request now came back from the optimized Arm lane. Its new receipt
> records KleidiAI on, and the ticket history ties the serving change to the
> EXP-2026-014 audit that approved it.

### 2:17-2:45 - Give The Mechanism To Another Developer

Click **Carry this release gate to another service**. Point to **Structure
valid**, the contract digest, workflow and download link.

> ArmProof now generates a complete starter for another HTTP AI service,
> including exact evidence templates, representative workloads, a collection
> plan and a GitHub Action. It remains blocked until that developer collects and
> seals their own measurements, so nobody can inherit our result by accident.

Stop recording on the generated workflow and download link.

## 6. Recording Accuracy

- The two support messages are live model inference and are entered during the video.
- The ten 500-second windows were collected before recording. The video reruns
  their verification from the checked-in archive.
- The capacity claim comes from the preregistered confirmation rates. Earlier
  discovery runs remain in the repository history and do not approve this release.
- INT4 size and memory results describe the BF16-to-INT4 migration. The
  two-times capacity result isolates KleidiAI within the matched INT4 runtime.
- Performix function samples and Linux perf cycle samples are reported as
  separate measurements.
- Human operators choose the final support queue. The queue guard is an
  application feature rather than part of the Arm speed claim.
- ArmProof evaluates this project's contract and evidence; it is not an Arm
  certification service.

## 7. Stop The Paid Host

Stop both service terminals, the SSH tunnel and the local gateway with
`Ctrl-C`, then terminate the instance:

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

Expected first output: the instance ID followed by `shutting-down`.
