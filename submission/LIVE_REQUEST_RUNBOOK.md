# Live Matched-Request Runbook

This adds a short live moment to the video without replacing the sustained
capacity evidence. It is an **illustration**, not a benchmark or capacity
claim.

## What The Recording Uses

One `c8g.4xlarge` runs two already-warm Phi-4 Mini INT4 processes:

- cores `0-7`: KleidiAI-disabled overlay on port `8001`;
- cores `8-15`: KleidiAI-enabled overlay on port `8002`.

The split prevents the two requests from competing for the same cores. It is
not the 16-thread configuration used by EXP-2026-009, so the displayed request
ratio must not be quoted as a project result. EXP-2026-009 remains the
authoritative same-instance capacity proof.

## Local Dry Run

The integration test starts two temporary loopback endpoints, sends the same
prompt concurrently, verifies the backend labels and rejects a swapped label:

```bash
PYTHONPATH=src python3.12 -m unittest tests.test_demo_live_compare -v
```

The checked dry run completed successfully on 2026-08-04. Its synthetic timing
is only an orchestration check.

## Graviton Preparation

1. Provision the existing guarded `c8g.4xlarge` recipe. Restore the pinned
   runtime and model files documented in `examples/phi4-graviton/README.md`.
2. Create the matched overlays:

   ```bash
   PYTHONPATH=src python3.12 scripts/prepare_phi4_variants.py \
     --source /models/phi4-int4 \
     --output-root /models/armproof-variants \
     --threads 8
   ```

3. In Graviton terminal A, start the disabled control:

   ```bash
   taskset -c 0-7 env OMP_NUM_THREADS=8 PYTHONPATH=src \
     python3.12 -m armproof.reference.phi4 \
     --backend ort-int4 \
     --model /models/armproof-variants/kleidiai-disabled \
     --label ort-int4-kleidiai-disabled \
     --port 8001 --threads 8 --max-inflight 1
   ```

4. In Graviton terminal B, start the enabled treatment:

   ```bash
   taskset -c 8-15 env OMP_NUM_THREADS=8 PYTHONPATH=src \
     python3.12 -m armproof.reference.phi4 \
     --backend ort-int4 \
     --model /models/armproof-variants/kleidiai-enabled \
     --label ort-int4-kleidiai-enabled \
     --port 8002 --threads 8 --max-inflight 1
   ```

5. From the recording machine, open one SSH tunnel:

   ```bash
   ssh -N \
     -L 18001:127.0.0.1:8001 \
     -L 18002:127.0.0.1:8002 \
     ubuntu@GRAVITON_HOST
   ```

6. Run the comparison once before recording to warm and validate both paths,
   then clear the terminal:

   ```bash
   python3.12 scripts/demo_live_compare.py \
     --baseline-endpoint http://127.0.0.1:18001/infer \
     --optimized-endpoint http://127.0.0.1:18002/infer
   ```

The command must print both expected backend labels. Any missing, swapped or
failed endpoint exits nonzero. Do not record until both are correct.

## Recording Sequence

1. Keep both services and the SSH tunnel running and warm.
2. Put the comparison command in a terminal without executing it.
3. Start video recording on the SurgeDesk triage view.
4. At `0:15`, switch to the terminal and press Enter once.
5. Leave the terminal visible until both results and the capacity disclaimer
   print; do not edit, replay or rerun the output.
6. Return to SurgeDesk and continue the sustained-evidence story.
7. After recording, stop both model processes, close the tunnel and terminate
   the EC2 instance with the guarded cleanup command. Confirm inventory is
   empty.

## Failure Rule

If either endpoint fails, returns the wrong backend label or produces an
ambiguous result, omit the live race rather than substituting synthetic output.
