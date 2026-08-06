# Live Graviton Deployment

This runbook starts the standard and released services on one AWS
Graviton4 host, verifies their identities, and connects them to SurgeDesk. It
is a live product-validation path; sustained-capacity evidence is collected by
the separate [benchmark protocol](BENCHMARK_PROTOCOL.md).

## Prerequisites

- AWS `c8g.4xlarge` running Ubuntu 24.04 Arm64
- SSH access to the instance
- Python 3.12 locally
- The checksum-pinned runtime bundle from the `v0.9.0` release

From the repository root, set:

```bash
export GRAVITON_HOST=ubuntu@YOUR_PUBLIC_DNS_NAME
export INSTANCE_ID=i-YOUR_INSTANCE_ID
export RUNTIME_BUNDLE="$PWD/runtime-checkpoints.tar.gz"
export RUNTIME_BUNDLE_SHA256=400a1c9d9050f4fc73836f51e1b8745f462ff305408c992fccd9dcbe78513984
```

Download and verify the runtime if it is not already present:

```bash
if [ ! -f "$RUNTIME_BUNDLE" ]; then
  curl -fL \
    https://github.com/QasimKhan5x/ArmProof/releases/download/v0.9.0/runtime-checkpoints.tar.gz \
    -o "$RUNTIME_BUNDLE"
fi
echo "$RUNTIME_BUNDLE_SHA256  $RUNTIME_BUNDLE" | shasum -a 256 -c -
ssh "$GRAVITON_HOST" 'uname -m'
```

Expected output includes `runtime-checkpoints.tar.gz: OK` and `aarch64`.

## Prepare The Host

```bash
scp "$RUNTIME_BUNDLE" "$GRAVITON_HOST:~/runtime-checkpoints.tar.gz"
ssh "$GRAVITON_HOST" '
  if [ -d ~/ArmProof/.git ]; then
    git -C ~/ArmProof pull --ff-only
  else
    git clone https://github.com/QasimKhan5x/ArmProof.git ~/ArmProof
  fi
  ~/ArmProof/scripts/prepare_graviton_host.sh
'
```

The final line begins with `READY` and reports the model identity, source
artifact identity, and `threads=16`. Setup verifies the runtime wheels and
downloaded model before starting either service.

Host preparation installs mimalloc and selects `always` for transparent huge
pages. The startup scripts refuse to run if that policy or the allocator library
is unavailable.

## Start The Release Lanes

Keep each command running in a separate terminal.

Control service:

```bash
ssh -t "$GRAVITON_HOST" '~/ArmProof/scripts/run_graviton_lane.sh baseline'
```

Released service (KleidiAI, ONNX Runtime thread tuning, mimalloc, and
transparent huge pages):

```bash
ssh -t "$GRAVITON_HOST" '~/ArmProof/scripts/run_graviton_lane.sh optimized'
```

SSH tunnel:

```bash
ssh -N \
  -L 18001:127.0.0.1:8001 \
  -L 18002:127.0.0.1:8002 \
  "$GRAVITON_HOST"
```

Each service verifies the runtime-artifact ledger and reads its EC2 instance
type through AWS IMDSv2. An identity mismatch prevents startup.

## Verify Endpoint Identity

```bash
python3.12 scripts/preflight_live_endpoints.py \
  --baseline-endpoint http://127.0.0.1:18001/infer \
  --optimized-endpoint http://127.0.0.1:18002/infer
```

Expected ending:

```text
READY matched endpoint identities verified; request latency is a warm-up observation.
```

The preflight checks that model, runtime, instance, architecture, thread count,
and CPU affinity match. It also requires opposite `mlas.disable_kleidiai`
controls, the exact three ONNX Runtime scheduling options on the released lane,
the system allocator on the standard lane, mimalloc on the released lane, and
transparent huge pages on both.
It sends one warm-up request to each service; that request is not capacity
evidence.

## Connect SurgeDesk

```bash
python3.12 scripts/serve_surgedesk.py \
  --port 8765 \
  --baseline-endpoint http://127.0.0.1:18001/infer \
  --optimized-endpoint http://127.0.0.1:18002/infer \
  --baseline-cores 0-15 \
  --optimized-cores 0-15
```

Open <http://127.0.0.1:8765/surgedesk/#triage>. In connected mode:

1. A customer message reaches the active control and the treatment shadow.
2. A person chooses the final support queue.
3. ArmProof re-derives the accepted capacity, quality, Performix, runtime-screen,
   paired sustained, and failed-simplification evidence.
4. The gateway compares both live deployments with the accepted identity.
5. The treatment becomes active only after the contract and deployment checks pass.
6. Every treatment response is checked again for runtime drift.

The checked-in KleidiAI capacity result comes from ten 500-second windows. The
runtime recipe has its own short screen, sustained comparison, and rejected
simplification. The live request
flow demonstrates deployment behavior and does not replace either measurement;
the two live lanes intentionally represent the standard and final released
service, not a one-variable causal benchmark.

## Verify The Adoption Path

Create a blocked-by-default project for another HTTP inference service:

```bash
STARTER="$(mktemp -d)/card-support"
PYTHONPATH=src python3.12 -m armproof.cli init \
  --endpoint http://127.0.0.1:18002/infer \
  --output "$STARTER"
PYTHONPATH=src python3.12 -m armproof.cli ci "$STARTER/armproof.json"
```

The initial check reports `No measured evidence found`. The generated project
can pass only after its developer collects evidence, replaces placeholders,
and seals the evidence ledger.

## Shut Down

Stop the service terminals, tunnel, and local gateway with `Ctrl-C`, then
terminate the paid instance:

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
