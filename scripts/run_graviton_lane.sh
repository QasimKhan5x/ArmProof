#!/usr/bin/env bash
set -Eeuo pipefail

LANE="${1:?usage: run_graviton_lane.sh baseline|optimized}"
ROOT="${2:-$HOME/ArmProof}"
VENV="${3:-$HOME/armproof-venv}"
MODELS="${4:-$HOME/armproof-models}"

case "$LANE" in
  baseline)
    LABEL="kleidiai-disabled"
    PORT=8001
    ;;
  optimized)
    LABEL="kleidiai-enabled"
    PORT=8002
    ;;
  *)
    echo "lane must be baseline or optimized" >&2
    exit 2
    ;;
esac

cd "$ROOT"
exec taskset -c 0-15 env OMP_NUM_THREADS=16 OMP_PROC_BIND=close OMP_PLACES=cores PYTHONPATH=src \
  "$VENV/bin/python" -m armproof.reference.phi4 \
  --backend ort-int4 \
  --model "$MODELS/variants/$LABEL" \
  --label "$LABEL" \
  --runtime-lock examples/phi4-graviton/runtime-lock.json \
  --runtime-artifact-ledger "$HOME/runtime-checkpoints/SHA256SUMS" \
  --runtime-artifact-ledger-sha256 2ac3491c5ce6d6b1dc178f27568b1e6e66b9b76031bc488143e72d9e7488d8c7 \
  --expected-instance-type c8g.4xlarge \
  --port "$PORT" --threads 16 --max-inflight 1
