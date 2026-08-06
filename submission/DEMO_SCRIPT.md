# Three-Minute Demo: Setup, Actions, And Narration

This is the only runbook needed to record the submission. The video follows one
service release from a real customer request to measured Arm evidence, traffic
promotion, and a second request on the approved route. Target length: **2:55**.

## 1. Verify The Repository On The Mac

From the repository root:

```bash
make check
npm run test:logic
npm run test:ui
PYTHONPATH=src python3.12 -m armproof.cli ci \
  examples/armproof-reference/armproof.json
```

Expected: all test suites pass and the final ArmProof command exits with code
`0` after approving the confirmed contract.

## 2. Prepare The Graviton4 Host

Run this section from the Mac. The SSH commands install and start the software
on AWS, not locally.

```bash
export GRAVITON_HOST=ubuntu@YOUR_PUBLIC_DNS_NAME
export INSTANCE_ID=i-YOUR_INSTANCE_ID
export RUNTIME_BUNDLE="$PWD/runtime-checkpoints.tar.gz"
export RUNTIME_BUNDLE_SHA256=400a1c9d9050f4fc73836f51e1b8745f462ff305408c992fccd9dcbe78513984

if [ ! -f "$RUNTIME_BUNDLE" ]; then
  curl -fL \
    https://github.com/QasimKhan5x/ArmProof/releases/download/v0.9.0/runtime-checkpoints.tar.gz \
    -o "$RUNTIME_BUNDLE"
fi
echo "$RUNTIME_BUNDLE_SHA256  $RUNTIME_BUNDLE" | shasum -a 256 -c -
ssh "$GRAVITON_HOST" 'uname -m'
```

Expected output includes `runtime-checkpoints.tar.gz: OK` and `aarch64`.

Upload the pinned runtime bundle and prepare the two model variants:

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

The final line begins with `READY` and prints the model and source hashes plus
`threads=16`. The setup verifies the runtime wheel checksums and downloaded
model before either service starts.

## 3. Start The Two Arm Configurations

Keep each command running in its own Mac terminal.

Terminal A, standard service:

```bash
ssh -t "$GRAVITON_HOST" '~/ArmProof/scripts/run_live_demo_lane.sh baseline'
```

Terminal B, optimized service:

```bash
ssh -t "$GRAVITON_HOST" '~/ArmProof/scripts/run_live_demo_lane.sh optimized'
```

At startup, each service verifies the runtime-artifact ledger and reads the EC2
instance type through AWS IMDSv2. A mismatch stops startup.

Terminal C, SSH tunnel:

```bash
ssh -N \
  -L 18001:127.0.0.1:8001 \
  -L 18002:127.0.0.1:8002 \
  "$GRAVITON_HOST"
```

## 4. Preflight And Start The Demo Gateway

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

Now start a fresh gateway. This resets the active route to the standard service
and clears any earlier release decision:

```bash
python3.12 scripts/serve_surgedesk.py \
  --port 8765 \
  --baseline-endpoint http://127.0.0.1:18001/infer \
  --optimized-endpoint http://127.0.0.1:18002/infer \
  --baseline-cores 0-15 \
  --optimized-cores 0-15
```

Open <http://127.0.0.1:8765/surgedesk/#triage>. The page detects the two matched
services and selects the connected Arm64 service automatically. Confirm that the
message box is empty. Rehearse once, restart the gateway, and refresh the page
before recording.

## 5. Record The Video

Record at 1440×900 or 1920×1080 with 100% browser zoom. Hide terminals,
bookmarks, notifications, and unrelated tabs. Speak while typing; do not begin
with silent setup.

### 0:00-0:38 — A Real Request Reaches The Standard Service

Type this message while beginning the narration:

```text
My card was stolen while I am travelling. Freeze it and help me replace it.
```

Click **Compare current route with Arm candidate** by `0:10`. The gateway sends
the request to the active standard service and then to the candidate on the same
16-core group. Point to the two fresh request receipts and the candidate's
`shadow only` label. Confirm **Account security**, click **Route ticket**, then
click **Check the Arm optimization**.

Say:

> SurgeDesk is the banking-support application. ArmProof is its reusable Arm
> optimization release gate. This stolen-card message goes to the standard
> service and then to the KleidiAI candidate as a shadow request. Both choose
> Account security, and these receipts came from Graviton just now. The standard
> route stays active until the measured release contract passes.

### 0:38-1:23 — Recalculate The Decision From Measured Evidence

Click **Recompute release decision**. Let the five checks finish, then click
**Open confirmed result**. Point to the two traffic rates, five-of-five outcomes,
and application-quality cell. Leave the blocked predecessor collapsed.

Say:

> ArmProof has now rechecked the saved evidence and recalculated the decision.
> The ten long windows were collected earlier; this action reopens their raw
> request rows and runs the release calculation again.
> Discovery first located each service's capacity boundary; we committed these
> two rates before launching the confirmation. The standard service then missed
> the ten-second p95 rule in all five runs at 0.28 requests per second. The
> optimized service passed all five at 0.56 requests per second, which is 2,016
> offered messages per hour. Standard capacity is therefore below 0.28, while
> optimized capacity is at least 0.56: a supported lower bound of two times,
> with quality still inside the one-point limit.

### 1:23-1:58 — Show The Arm Path, Then Switch Traffic

Click **Review and switch live traffic**. Point first to the summary and then to
the Performix fractions. Click **Switch live traffic to optimized service** and
point to the route receipt and the AWS/Arm placement row.

Say:

> The model files, workload, runtime build, Graviton4 machine, and 16-core
> placement stayed fixed. Only the KleidiAI control changed. Arm Performix found
> zero KleidiAI function samples in the control and 67 percent in the treatment,
> including the Neoverse I8MM matrix kernel. Before switching traffic, the
> gateway matches the live model, runtime ledger, AWS instance, cores, and
> KleidiAI setting to the release that just passed.

### 1:58-2:55 — End On A Different Request Served By The Optimized Lane

Click **Send a request through the optimized service**. Type a different message:

```text
My card is about to expire. How do I get a replacement?
```

Click **Run optimized live route**, review the proposed queue, and click **Route
ticket**. End the recording on the cutover summary and the two live ticket
receipts.

Say:

> This second customer message is now using the optimized route. Its new receipt
> shows KleidiAI on and names the experiment that authorized the switch. After I
> confirm the queue, SurgeDesk shows the standard request from before release
> beside this optimized request, backed by at least twice the measured sustainable
> capacity on the same server.

## 6. What Each Action Proves

- **Live requests:** the shadow comparison and post-release request execute on
  the connected Graviton service and return current request and runtime receipts.
- **Evidence validation:** **Recompute release decision** hashes the checked-in
  capacity rows, quality outputs and Performix profiles, re-derives their
  metrics, and evaluates the release contract during the recording.
- **Full recollection:** rerunning all ten 500-second capacity windows requires
  the separate Graviton benchmark workflow documented in
  `docs/BENCHMARK_PROTOCOL.md`.
- The two capacity rates differ intentionally. They establish a boundary:
  standard capacity is below 0.28 requests/s, while optimized capacity is at
  least 0.56 requests/s.
- INT4 model-size and memory gains are a separate BF16-to-INT4 migration result.
  The two-times capacity result isolates KleidiAI inside the matched INT4 setup.
- The service verifies the supplied runtime-wheel artifacts and obtains the EC2
  instance type from IMDSv2. These checks validate deployment identity; the
  project does not claim hardware-backed remote attestation.
- Every optimized request is compared again with the accepted release identity.
  Drift blocks the response, invalidates the release, and returns the gateway to
  the standard lane.
- ArmProof evaluates a declared optimization contract; it is not an Arm
  certification service.

## 7. Verify The Adoption Path After Recording

This is a repository check, not part of the three-minute video. It points a new
ArmProof project at the candidate endpoint used above:

```bash
DEMO_STARTER="$(mktemp -d)/card-support" && \
PYTHONPATH=src python3.12 -m armproof.cli init \
  --endpoint http://127.0.0.1:18002/infer \
  --output "$DEMO_STARTER"
PYTHONPATH=src python3.12 -m armproof.cli ci "$DEMO_STARTER/armproof.json"
ARM_GATE_EXIT=$?
test "$ARM_GATE_EXIT" -eq 1
```

Expected output includes `Created 17 files`, the location of
`ADOPTION_CHECKLIST.md`, and `No measured evidence found`. The final `test`
confirms the expected fail-closed exit. The generated project can pass only
after its developer collects and seals measurements.

## 8. Stop AWS Billing

Stop the two service terminals, tunnel, and local gateway with `Ctrl-C`, then:

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
