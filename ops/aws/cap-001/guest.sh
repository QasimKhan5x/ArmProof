#!/usr/bin/env bash
set -Eeuo pipefail

case "${EXPERIMENT_APPROVAL_TOKEN:-}" in
  exp-2026-003-capacity)
    EXPERIMENT_ID="EXP-2026-003"
    PROTOCOL_PATH="ops/aws/cap-001/protocol.json"
    ;;
  exp-2026-004-capacity)
    EXPERIMENT_ID="EXP-2026-004"
    PROTOCOL_PATH="ops/aws/cap-002/protocol.json"
    ;;
  exp-2026-005-reproduction)
    EXPERIMENT_ID="EXP-2026-005"
    PROTOCOL_PATH="ops/aws/repro-001/protocol.json"
    WATCHDOG_MINUTES=115
    ;;
  exp-2026-006-sustained)
    EXPERIMENT_ID="EXP-2026-006"
    PROTOCOL_PATH="ops/aws/sustained-001/protocol.json"
    WATCHDOG_MINUTES=235
    ;;
  exp-2026-007-isolated-sustained)
    EXPERIMENT_ID="EXP-2026-007"
    PROTOCOL_PATH="ops/aws/sustained-002/protocol.json"
    WATCHDOG_MINUTES=265
    ;;
  *) exit 64 ;;
esac

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
  cd "$ROOT"
  tar -czf /tmp/armproof-evidence.tar.gz evidence
  curl -fsS -X PUT -T /tmp/armproof-evidence.tar.gz "$RESULT_UPLOAD_URL"
  shutdown -h now
}
trap upload_results EXIT

# Independent guest watchdog; the controller has a separate immutable deadline.
shutdown -h +"${WATCHDOG_MINUTES:-115}"
curl -fsSL "$PROJECT_BUNDLE_URL" -o /tmp/project.tar.gz
echo "$PROJECT_BUNDLE_SHA256  /tmp/project.tar.gz" | sha256sum -c -
tar -xzf /tmp/project.tar.gz -C "$WORK"
cd "$WORK"

date --iso-8601=seconds > "$RESULTS/started-at.txt"
uname -a > "$RESULTS/uname.txt"
lscpu > "$RESULTS/lscpu.txt"
cat /proc/cpuinfo > "$RESULTS/cpuinfo.txt"
cp examples/phi4-graviton/runtime-lock.json "$RESULTS/runtime-lock.json"
cp "ops/experiments/$EXPERIMENT_ID.json" "$RESULTS/experiment.json"
cp "$PROTOCOL_PATH" "$RESULTS/protocol.json"

apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-dev python3-venv curl linux-tools-common linux-tools-generic
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

export PYTHONPATH="$WORK/src"
export OMP_NUM_THREADS=16
export OMP_PROC_BIND=close
export OMP_PLACES=cores
set +e
QUALITY_ARGS=()
if [[ "$EXPERIMENT_ID" == "EXP-2026-004" || "$EXPERIMENT_ID" == "EXP-2026-005" || "$EXPERIMENT_ID" == "EXP-2026-006" || "$EXPERIMENT_ID" == "EXP-2026-007" ]]; then
  mkdir -p "$ROOT/quality-reuse"
  curl -fsSL "$QUALITY_DISABLED_URL" -o "$ROOT/quality-reuse/kleidiai-disabled.json"
  echo "$QUALITY_DISABLED_SHA256  $ROOT/quality-reuse/kleidiai-disabled.json" | sha256sum -c -
  curl -fsSL "$QUALITY_ENABLED_URL" -o "$ROOT/quality-reuse/kleidiai-enabled.json"
  echo "$QUALITY_ENABLED_SHA256  $ROOT/quality-reuse/kleidiai-enabled.json" | sha256sum -c -
  QUALITY_ARGS=(--precomputed-quality-dir "$ROOT/quality-reuse")
fi
"$ROOT/venv/bin/python" scripts/run_cap_001.py \
  --model-source "$MODEL_SOURCE" --output "$RESULTS/capacity" \
  --protocol "$PROTOCOL_PATH" "${QUALITY_ARGS[@]}" | tee "$RESULTS/capacity.stdout.json"
CAP_STATUS=${PIPESTATUS[0]}
set -e

for treatment in disabled enabled; do
  perf record -F 99 -g -o "$RESULTS/perf-$treatment.data" -- \
    "$ROOT/venv/bin/python" scripts/profile_ort.py \
      --model "$RESULTS/capacity/variants/$treatment" \
      --workload data/banking77/generated/traffic-mixed.jsonl --repetitions 3
  perf report --stdio -i "$RESULTS/perf-$treatment.data" > "$RESULTS/perf-$treatment.txt" 2>&1
done
grep -q 'kai_' "$RESULTS/perf-enabled.txt"
if grep -q 'kai_' "$RESULTS/perf-disabled.txt"; then
  echo 'disabled control unexpectedly contains kai_ callchains' >&2
  exit 70
fi

find "$RESULTS" -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > "$RESULTS/SHA256SUMS"
date --iso-8601=seconds > "$RESULTS/completed-at.txt"
exit "$CAP_STATUS"
