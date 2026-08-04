# SurgeDesk Three-Minute Demo

This is the complete setup, recording, and cleanup runbook. The video stays in
one browser window. Its two live moments are six matched Graviton requests and
a fresh ArmProof audit of the sustained evidence archive.

Target recording length: **2:45 to 2:58**.

## 1. Validate The Repository

Run from the repository root on the recording Mac:

```bash
PYTHONPATH=src python3.12 -m unittest discover -s tests
npm run test:logic
```

Expected ending:

```text
OK
# pass 4
# fail 0
```

The canonical release check should report the same result shown in SurgeDesk:

```bash
python3.12 scripts/demo_release_gate.py
```

Expected output:

```text
PASS    9/9 claims from 4,200 raw request outcomes
RELEASE at least 2.00x sustainable capacity
BLOCK   altered archive refused before derivation
```

## 2. Prepare One Graviton4 Instance

Use an Ubuntu 24.04 Arm64 `c8g.4xlarge` in `us-east-1`. Set the values returned
by EC2, then upload the pinned runtime bundle already present beside this repo:

```bash
export GRAVITON_HOST=ubuntu@YOUR_PUBLIC_DNS_NAME
export INSTANCE_ID=i-YOUR_INSTANCE_ID
export RUNTIME_BUNDLE="$(cd .. && pwd)/result-first-bakeoff/evidence/checkpoints/runtime-checkpoints.tar.gz"

test -f "$RUNTIME_BUNDLE"
ssh "$GRAVITON_HOST" 'uname -m'
scp "$RUNTIME_BUNDLE" "$GRAVITON_HOST:~/runtime-checkpoints.tar.gz"
```

Expected: `uname -m` prints `aarch64` and `scp` reaches `100%`.

On the Graviton host:

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

Expected: every `sha256sum` row ends in `OK`, and
`~/models/armproof-variants` contains `kleidiai-disabled` and
`kleidiai-enabled`.

## 3. Start The Matched Services

Open two SSH terminals and leave both commands running.

Graviton terminal A, cores `0-7`:

```bash
cd ~/ArmProof
taskset -c 0-7 env OMP_NUM_THREADS=8 PYTHONPATH=src \
  ~/armproof-venv/bin/python -m armproof.reference.phi4 \
  --backend ort-int4 \
  --model ~/models/armproof-variants/kleidiai-disabled \
  --label kleidiai-disabled \
  --port 8001 --threads 8 --max-inflight 1
```

Graviton terminal B, cores `8-15`:

```bash
cd ~/ArmProof
taskset -c 8-15 env OMP_NUM_THREADS=8 PYTHONPATH=src \
  ~/armproof-venv/bin/python -m armproof.reference.phi4 \
  --backend ort-int4 \
  --model ~/models/armproof-variants/kleidiai-enabled \
  --label kleidiai-enabled \
  --port 8002 --threads 8 --max-inflight 1
```

## 4. Connect The Browser

Open an SSH tunnel on the recording Mac and leave it running:

```bash
ssh -N \
  -L 18001:127.0.0.1:8001 \
  -L 18002:127.0.0.1:8002 \
  "$GRAVITON_HOST"
```

In another local terminal, inspect both runtime identities:

```bash
curl -s http://127.0.0.1:18001/health | jq '{backend,architecture,cpu_affinity,runtime,runtime_version,model_identity,optimization_control,threads}'
curl -s http://127.0.0.1:18002/health | jq '{backend,architecture,cpu_affinity,runtime,runtime_version,model_identity,optimization_control,threads}'
```

Expected: both rows show the same 64-character `model_identity`, runtime
version, and eight threads. Their affinity lists are disjoint, and the only
configuration difference is the declared control:

```json
{"backend":"kleidiai-disabled","architecture":"aarch64","cpu_affinity":[0,1,2,3,4,5,6,7],"runtime":"onnxruntime-genai","model_identity":"<same digest>","optimization_control":{"mlas.disable_kleidiai":"1"},"threads":8}
{"backend":"kleidiai-enabled","architecture":"aarch64","cpu_affinity":[8,9,10,11,12,13,14,15],"runtime":"onnxruntime-genai","model_identity":"<same digest>","optimization_control":{"mlas.disable_kleidiai":"0"},"threads":8}
```

Warm both models once:

```bash
python3.12 scripts/demo_live_compare.py \
  --baseline-endpoint http://127.0.0.1:18001/infer \
  --optimized-endpoint http://127.0.0.1:18002/infer
```

Both backend names must appear. The individual latency ratio can vary because
this is one warm-up request.

Start the demo gateway:

```bash
python3.12 scripts/serve_surgedesk.py \
  --port 8765 \
  --baseline-endpoint http://127.0.0.1:18001/infer \
  --optimized-endpoint http://127.0.0.1:18002/infer
```

Expected:

```text
SurgeDesk: http://127.0.0.1:8765/surgedesk/
Live route: configured; enabled after runtime identity probe
Matched request check: configured; enabled after matched identity probes
```

Open [http://127.0.0.1:8765/surgedesk/](http://127.0.0.1:8765/surgedesk/).
At 100% zoom, confirm that **Live matched Arm64 endpoint** is selectable and the
capacity tab says **Matched Arm endpoints connected**.

## 5. Stage The Browser

1. Open **1. Support workflow** and select **Live matched Arm64 endpoint**.
2. Enter: `My card was stolen and I need it frozen now`.
3. Leave the request unsubmitted.
4. Close unrelated tabs, hide notifications, and start recording.

## 6. Record The Video

### 0:00-0:12

**Show:** The live request ready in SurgeDesk.

**Say:**

> SurgeDesk is a banking-support triage service running Phi-4 Mini INT4 on one
> Graviton4 server. I’ll route one live request, then show exactly why the
> optimized service was approved for more traffic.

### 0:12-0:32

**Do:** Click **Run live route**. When the suggestion appears, point briefly to
the live backend and queue, then click **Confirm route** and **Open platform
capacity audit**.

**Say:**

> The model proposes the issue and procedure, a small routing guard chooses the
> security queue, and the support agent confirms the action. Now I’m handing the
> deployment question to the platform engineer.

### 0:32-0:55

**Do:** On **2. Capacity audit**, leave the same customer message in place and
click **Run matched request check**. Let all six tiles finish.

**Say:**

> Each service hashed its local model files at startup. The gateway has matched
> those hashes, the ONNX Runtime version and eight threads per lane, while
> keeping their CPU affinities disjoint. It checks the identity again on every
> response. This short request check proves the live setup. The long audit below
> carries the capacity claim.

### 0:55-1:35

**Do:** Click **Verify measured experiment**. Wait for the audit to finish,
then point to the four completed checks, the trial rows and the equation.

**Say:**

> The original experiment tried to establish an exact two-to-two-point-five
> times capacity bracket. That required all five optimized runs at 0.60 requests
> per second to fail. One passed, so the preregistered bracket was rejected.
> These twenty 500-second windows took nearly three hours; what ran just now was
> the audit. It checked the archive and recomputed all 4,200 outcomes. Every
> control run failed at 0.28, and every optimized run passed at 0.56. ArmProof
> therefore evaluates a different, narrower claim: 0.56 divided by the failing
> 0.28 baseline proves at least twice the sustainable traffic.

### 1:35-1:58

**Do:** Point to **Causal Arm evidence**, then open **3. Release gate** and stop
on the Performix panel.

**Say:**

> The capacity test changed one declared runtime control. Arm Performix found
> no KleidiAI function samples in the control and 67.02 percent in the treatment,
> including the Neoverse I8MM kernel. Linux perf independently measured 68.53
> percent of cycles in that call chain.

### 1:58-2:22

**Do:** Scroll to **The same fail-closed method runs in pull requests** and
click **Test a one-byte evidence change**.

**Say:**

> I’ll change one byte in a temporary copy of the evidence bundle. The digest no
> longer matches, so ArmProof stops before calculating any metric and blocks the
> release. The same check runs as a GitHub Action on an optimization pull request.

### 2:22-2:43

**Do:** Scroll to **Adoption path** and click **Generate a starter kit preview**.

**Say:**

> Another Arm developer can generate the same contract, evidence layout,
> profiler manifest and pull-request check for a bounded HTTP classification
> service. The new gate starts blocked and opens only after real measurements
> satisfy the project’s own thresholds.

### 2:43-2:52

**Say:**

> SurgeDesk shows the user outcome. ArmProof makes the Arm optimization
> reviewable, reproducible and safe to release.

Stop recording.

## 7. Accuracy Rules

- The live tiles illustrate one short request burst. The sustained audit proves
  capacity.
- The loaded archive contains recorded measurement evidence; the verification
  itself runs during the video.
- The BF16-to-INT4 footprint gains and the KleidiAI capacity gain have separate
  causal scopes.
- The queue guard improves application routing and is separate from the Arm
  optimization.
- ArmProof verifies the submitted contract and evidence. It does not represent
  official Arm certification.

## 8. Stop AWS

Press `Ctrl-C` in the two service terminals, tunnel, and local gateway. Then:

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
