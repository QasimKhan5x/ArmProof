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
    MEMORY_ENV=(-u LD_PRELOAD)
    ;;
  optimized)
    LABEL="kleidiai-enabled"
    PORT=8002
    MIMALLOC_LIB="$(ldconfig -p | awk '/libmimalloc\.so/{print $NF; exit}')"
    test -n "$MIMALLOC_LIB"
    MEMORY_ENV=("LD_PRELOAD=$MIMALLOC_LIB")
    ;;
  *)
    echo "lane must be baseline or optimized" >&2
    exit 2
    ;;
esac

grep -q '\[always\]' /sys/kernel/mm/transparent_hugepage/enabled || {
  echo "transparent huge pages must be set to always before either lane starts" >&2
  exit 1
}

cd "$ROOT"
exec taskset -c 0-15 env "${MEMORY_ENV[@]}" OMP_NUM_THREADS=16 OMP_PROC_BIND=close OMP_PLACES=cores PYTHONPATH=src \
  "$VENV/bin/python" -m armproof.reference.phi4 \
  --backend ort-int4 \
  --model "$MODELS/variants/$LABEL" \
  --label "$LABEL" \
  --runtime-lock examples/phi4-graviton/runtime-lock.json \
  --runtime-artifact-ledger "$HOME/runtime-checkpoints/SHA256SUMS" \
  --runtime-artifact-ledger-sha256 2ac3491c5ce6d6b1dc178f27568b1e6e66b9b76031bc488143e72d9e7488d8c7 \
  --expected-instance-type c8g.4xlarge \
  --port "$PORT" --threads 16 --max-inflight 1
