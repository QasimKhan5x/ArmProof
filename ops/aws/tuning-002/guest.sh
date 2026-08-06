#!/usr/bin/env bash
set -Eeuo pipefail

[[ "${EXPERIMENT_APPROVAL_TOKEN:-}" == "exp-2026-016-thp-isolation" ]] || exit 64

export HOME=/root
ROOT=/opt/armproof
WORK="$ROOT/work"
RESULTS="$ROOT/evidence"
MODELS="$ROOT/models"
mkdir -p "$WORK" "$RESULTS" "$MODELS"
exec > >(tee -a "$RESULTS/guest.log") 2>&1

upload_results() {
  status=$?
  set +e
  printf '%s\n' "$status" > "$RESULTS/exit-status.txt"
  date --iso-8601=seconds > "$RESULTS/finished-at.txt"
  find "$RESULTS" -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > "$RESULTS/SHA256SUMS"
  tar -C "$ROOT" -czf /tmp/armproof-tuning-evidence.tar.gz evidence
  curl -fsS -X PUT -T /tmp/armproof-tuning-evidence.tar.gz "$RESULT_UPLOAD_URL"
  shutdown -h now
}
trap upload_results EXIT

shutdown -h +32
curl -fsSL "$PROJECT_BUNDLE_URL" -o /tmp/project.tar.gz
echo "$PROJECT_BUNDLE_SHA256  /tmp/project.tar.gz" | sha256sum -c -
tar -xzf /tmp/project.tar.gz -C "$WORK"
cd "$WORK"

date --iso-8601=seconds > "$RESULTS/started-at.txt"
uname -a > "$RESULTS/uname.txt"
lscpu > "$RESULTS/lscpu.txt"
cat /sys/kernel/mm/transparent_hugepage/enabled > "$RESULTS/thp-before.txt"
cp ops/experiments/EXP-2026-016.json "$RESULTS/experiment.json"
cp ops/aws/tuning-002/protocol.json "$RESULTS/protocol.json"

apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-dev python3-venv curl
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libmimalloc-dev || true
python3 -m venv "$ROOT/venv"
"$ROOT/venv/bin/pip" install --upgrade pip
"$ROOT/venv/bin/pip" install -r ops/aws/cap-001/requirements.txt

curl -fsSL "$RUNTIME_CHECKPOINTS_URL" -o /tmp/runtime-checkpoints.tar.gz
echo "$RUNTIME_CHECKPOINTS_SHA256  /tmp/runtime-checkpoints.tar.gz" | sha256sum -c -
mkdir -p "$ROOT/runtime-checkpoints"
tar -xzf /tmp/runtime-checkpoints.tar.gz -C "$ROOT/runtime-checkpoints"
(cd "$ROOT/runtime-checkpoints" && sha256sum -c SHA256SUMS)
"$ROOT/venv/bin/pip" install --force-reinstall --no-deps \
  "$ROOT/runtime-checkpoints/onnxruntime-1.29.0-cp312-cp312-linux_aarch64.whl" \
  "$ROOT/runtime-checkpoints/onnxruntime_genai-0.15.0.dev0-cp312-cp312-linux_aarch64.whl"

export HF_HOME="$ROOT/hf-cache"
"$ROOT/venv/bin/hf" download microsoft/Phi-4-mini-instruct-onnx \
  --revision fc04c8f93df696602fd9f300a30d1bf2e3081347 \
  --include 'cpu_and_mobile/cpu-int4-rtn-block-32-acc-level-4/*' \
  --local-dir "$MODELS/onnx-repo"
MODEL_SOURCE="$MODELS/onnx-repo/cpu_and_mobile/cpu-int4-rtn-block-32-acc-level-4"
MIMALLOC=$(ldconfig -p | awk '/libmimalloc.so/{print $NF; exit}')
MIMALLOC_ARGS=()
if [[ -n "$MIMALLOC" ]]; then MIMALLOC_ARGS=(--mimalloc-library "$MIMALLOC"); fi

export PYTHONPATH="$WORK/src"
"$ROOT/venv/bin/python" scripts/run_runtime_tuning_015.py \
  --model-source "$MODEL_SOURCE" --output "$RESULTS/tuning" \
  --protocol ops/aws/tuning-002/protocol.json "${MIMALLOC_ARGS[@]}" \
  | tee "$RESULTS/tuning.stdout.json"

cat /sys/kernel/mm/transparent_hugepage/enabled > "$RESULTS/thp-after.txt"
date --iso-8601=seconds > "$RESULTS/completed-at.txt"
