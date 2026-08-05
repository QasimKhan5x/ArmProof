# Three-Minute Demo: Setup, Actions, And Narration

This is the only runbook needed to record the submission. The video contains
two real customer inputs, a fresh shadow comparison, a release decision
recomputed from measured evidence, a live route switch, and a starter generated
during the recording. Target length: **2:55**. Stop before **3:00**.

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
export RUNTIME_BUNDLE="$(cd .. && pwd)/result-first-bakeoff/evidence/checkpoints/runtime-checkpoints.tar.gz"

test -f "$RUNTIME_BUNDLE"
ssh "$GRAVITON_HOST" 'uname -m'
```

Expected output: `aarch64`.

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

Open <http://127.0.0.1:8765/surgedesk/#triage>, select **Live matched Arm64
endpoint**, and confirm that the message box is empty. Rehearse once, restart
the gateway, refresh the page, and select live mode again before recording.

## 5. Record The Video

Record at 1440×900 or 1920×1080 with 100% browser zoom. Hide terminals,
bookmarks, notifications, and unrelated tabs. Speak while typing; do not begin
with silent setup.

### 0:00-0:38 — Let A Real Request Challenge The Candidate

Type this message while beginning the narration:

```text
My card was stolen while I am travelling. Freeze it and help me replace it.
```

Click **Compare current route with Arm candidate** by `0:10`. The gateway runs
the serving configuration first and then sends a shadow copy to the optimized
configuration, avoiding contention between two services that each use all 16
cores. Point to the two fresh timings and the `shadow only` label. Confirm
**Account security**, click **Route ticket**, then click **Check the Arm
optimization**.

Say:

> SurgeDesk helps a bank operator route support messages. The standard service
> is serving; the Arm-optimized candidate remains blocked. I am sending one real
> message to the serving route and then to the candidate as a shadow copy. Both
> propose Account security, and these timings came from Graviton just now. One
> request is only illustrative, so the candidate still cannot serve customers.

### 0:38-1:18 — Turn Measurements Into A Release Decision

Click **Recompute release decision**. Let the five checks finish, then click
**Open confirmed result**. Point to the two traffic rates, five-of-five outcomes,
and application-quality cell. Leave the blocked predecessor collapsed.

Say:

> A promising request cannot change production. ArmProof hashes the evidence and
> rebuilds ten 500-second traffic tests. At 0.28 requests per
> second, the standard service missed the ten-second response target in every
> run. The optimized service passed every run at 0.56, twice the load,
> establishing at least twice the sustainable capacity. Operational queue
> accuracy is 86.75 percent. The 77-intent score changed by 0.39 points, inside
> the release limit; an operator confirms every route.

### 1:18-1:52 — Show Why Arm Made The Difference, Then Switch

Click **Review and switch live traffic**. Point first to the summary and then to
the Performix fractions. Click **Switch live traffic to optimized service** and
point to the route receipt and the AWS/Arm placement row.

Say:

> The model, workload, runtime, machine, and 16-core placement stayed fixed; only
> KleidiAI changed. Arm Performix found no KleidiAI functions in the standard
> profile and 245,876 samples in the optimized profile, including the Arm matrix
> kernel. The gateway matches model and source hashes, verifies the runtime-wheel
> ledger, reads the AWS instance type, and checks active cores. The optimized
> service is now live.

### 1:52-2:30 — Prove The New Route With A Different Live Request

Click **Send a request through the optimized service**. Type a different message:

```text
My card is about to expire. How do I get a replacement?
```

Click **Run optimized live route**, review the proposed queue, and click **Route
ticket**. Hold the cutover summary and the two ticket receipts for several
seconds.

Say:

> This second customer message is different from the first. Its fresh
> receipt shows KleidiAI on and ties the response to the accepted experiment.
> The operator confirms the queue, and the cutover record now shows the standard
> request before release, the optimized request after release, and the measured
> two-times capacity bound that authorized the change.

### 2:30-2:55 — End With The Community Artifact

Click **Generate a starter for another service**. Point to `16 files`, `BLOCKED`,
and `no measured evidence found`. Hold this final state until `2:55`.

Say:

> ArmProof is reusable outside SurgeDesk. This button just created a 16-file
> starter and ran its first CI check. It starts blocked because a new project has
> no measurements yet. Once a developer collects capacity, quality, identity,
> and profiler evidence, the same release engine evaluates that service's own
> contract.

## 6. Accuracy Boundaries

- The shadow comparison and post-release support request are live model
  inference. Their displayed timings are observations, not capacity proof.
- Capacity rows, quality outputs, and Performix profiles were collected earlier
  on Graviton4. The recording recomputes the decision from those checked-in
  files; it does not pretend to rerun 5,000 seconds of tests instantly.
- The two capacity rates differ intentionally. They establish a boundary:
  standard capacity is below 0.28 requests/s, while optimized capacity is at
  least 0.56 requests/s.
- INT4 model-size and memory gains are a separate BF16-to-INT4 migration result.
  The two-times capacity result isolates KleidiAI inside the matched INT4 setup.
- The service verifies the supplied runtime-wheel artifacts and obtains the EC2
  instance type from IMDSv2. This is deployment validation, not hardware-backed
  remote attestation.
- Every optimized request is compared again with the accepted release identity.
  Drift blocks the response, invalidates the release, and returns the gateway to
  the standard lane.
- ArmProof is an open-source release gate, not an Arm certification service.

## 7. Stop AWS Billing

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
