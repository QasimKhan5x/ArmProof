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

> SurgeDesk routes banking support messages. A faster Arm candidate is waiting,
> but a bank cannot switch production because one request looks good. ArmProof
> keeps it blocked while I send this stolen-card message to the standard service
> and an optimized shadow. Both choose Account security. These timings came from
> Graviton just now; the shadow still cannot serve customers.

### 0:38-1:18 — Turn Measurements Into A Release Decision

Click **Recompute release decision**. Let the five checks finish, then click
**Open confirmed result**. Point to the two traffic rates, five-of-five outcomes,
and application-quality cell. Leave the blocked predecessor collapsed.

Say:

> ArmProof now hashes the saved request rows from ten long Graviton traffic runs
> and recalculates the release. At 0.28 requests per second, the standard service
> missed the ten-second p95 limit in all five runs. The optimized service passed
> all five at twice the load: 0.56 requests per second, or 2,016 offered messages
> an hour. Routing quality remained inside the one-point release limit.

### 1:18-1:52 — Show Why Arm Made The Difference, Then Switch

Click **Review and switch live traffic**. Point first to the summary and then to
the Performix fractions. Click **Switch live traffic to optimized service** and
point to the route receipt and the AWS/Arm placement row.

Say:

> The model, workload, runtime, machine, and 16-core placement stayed fixed; only
> the KleidiAI runtime setting changed. Arm Performix found no KleidiAI functions
> in the standard profile and attributed 67 percent of the optimized profile to
> KleidiAI, including the Neoverse I8MM matrix kernel. The gateway rechecks the
> model, runtime files, AWS instance, and active cores before switching traffic.

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

### 2:30-2:58 — Hand Off The Tool, Then End On The Released Service

Click **Generate a starter for another service**. Point to `17 files`, `BLOCKED`,
and `no measured evidence found`. Then click **Return to released service** and
hold the cutover summary and both routed tickets until `2:58`.

Say:

> This button created ArmProof's contract, collection plan, and pull-request
> check for another service. That project starts blocked because it has no
> measurements; SurgeDesk earned release from its own evidence. The result is a
> measured Arm optimization changing a live service, with the same guardrail
> ready for another Arm developer.

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
