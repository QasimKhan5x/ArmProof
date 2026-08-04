#!/usr/bin/env bash
# Sourced by guest.sh after the exact committed project bundle is verified.

EXPERIMENT_ID=EXP-2026-013
MODELS="$ROOT/models"
mkdir -p "$MODELS" "$RESULTS/performix/runs" "$RESULTS/performix/exports"

date --iso-8601=seconds > "$RESULTS/started-at.txt"
uname -a > "$RESULTS/uname.txt"
lscpu > "$RESULTS/lscpu.txt"
cat /proc/cpuinfo > "$RESULTS/cpuinfo.txt"
cp examples/phi4-graviton/runtime-lock.json "$RESULTS/runtime-lock.json"
cp "ops/experiments/$EXPERIMENT_ID.json" "$RESULTS/experiment.json"

apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  python3-dev python3-venv python-is-python3 binutils curl jq numactl \
  linux-tools-common linux-tools-generic
sysctl -w kernel.perf_event_paranoid=-1 | tee "$RESULTS/perf-event-paranoid.txt"
sysctl -w kernel.kptr_restrict=0 | tee "$RESULTS/kptr-restrict.txt"

curl -fsSL "$RUNTIME_CHECKPOINTS_URL" -o /tmp/runtime-checkpoints.tar.gz
echo "$RUNTIME_CHECKPOINTS_SHA256  /tmp/runtime-checkpoints.tar.gz" | sha256sum -c -
mkdir -p "$ROOT/runtime-checkpoints"
tar -xzf /tmp/runtime-checkpoints.tar.gz -C "$ROOT/runtime-checkpoints"
(cd "$ROOT/runtime-checkpoints" && sha256sum -c SHA256SUMS)

curl -fsSL "$PERFORMIX_CLI_URL" -o /tmp/performix-cli.tar.gz
echo "$PERFORMIX_CLI_SHA256  /tmp/performix-cli.tar.gz" | sha256sum -c -
tar -xzf /tmp/performix-cli.tar.gz -C "$APX_ROOT"
chmod +x "$APX_ROOT/apx"
sha256sum /tmp/performix-cli.tar.gz "$APX_ROOT/apx" > "$RESULTS/performix-artifacts.sha256"

python3 -m venv "$ROOT/venv"
"$ROOT/venv/bin/pip" install --upgrade pip
"$ROOT/venv/bin/pip" install -r ops/aws/cap-001/requirements.txt
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
"$ROOT/venv/bin/python" scripts/prepare_phi4_variants.py \
  --source "$MODEL_SOURCE" --output-root "$ROOT/variants" --threads 16
"$ROOT/venv/bin/python" scripts/fingerprint_artifact.py "$MODEL_SOURCE" \
  > "$RESULTS/artifact-identities.json"
sha256sum data/banking77/generated/traffic-mixed.jsonl > "$RESULTS/workload.sha256"

export OMP_NUM_THREADS=16
export OMP_PROC_BIND=close
export OMP_PLACES=cores
PROFILE_BASE="$ROOT/venv/bin/python scripts/profile_ort.py"
PROFILE_TAIL="--workload data/banking77/generated/traffic-mixed.jsonl --repetitions 3"
DISABLED="$PROFILE_BASE --model $ROOT/variants/kleidiai-disabled $PROFILE_TAIL"
ENABLED="$PROFILE_BASE --model $ROOT/variants/kleidiai-enabled $PROFILE_TAIL"

"$APX_ROOT/apx" version | tee "$RESULTS/performix/version.txt"
"$APX_ROOT/apx" target list --json > "$RESULTS/performix/targets.json"
"$APX_ROOT/apx" recipe list --json > "$RESULTS/performix/recipes.json"
"$APX_ROOT/apx" target prepare --target localhost --json > "$RESULTS/performix/target-prepare.json"
"$APX_ROOT/apx" target info localhost --json > "$RESULTS/performix/target-info.json"
"$ROOT/venv/bin/python" scripts/profile_ort.py \
  --model "$ROOT/variants/kleidiai-disabled" \
  --workload data/banking77/generated/traffic-mixed.jsonl --repetitions 1
"$ROOT/venv/bin/python" scripts/profile_ort.py \
  --model "$ROOT/variants/kleidiai-enabled" \
  --workload data/banking77/generated/traffic-mixed.jsonl --repetitions 1

run_profile() {
  local treatment="$1" command="$2" stem="code_hotspots-$1"
  local output="$RESULTS/performix/runs/${stem}.run.jsonl"
  "$APX_ROOT/apx" recipe ready code_hotspots --target localhost \
    --workload "$command" --use-shell --working-dir "$WORK" \
    --param sampling_freq=normal --json > "$RESULTS/performix/runs/${stem}.ready.json"
  "$APX_ROOT/apx" recipe run code_hotspots --target localhost \
    --workload "$command" --use-shell --working-dir "$WORK" --deploy-tools \
    --param sampling_freq=normal --json | tee "$output"
  local run_id
  run_id=$("$ROOT/venv/bin/python" scripts/extract_performix_run_id.py < "$output")
  printf 'code_hotspots\t%s\t%s\n' "$treatment" "$run_id" >> "$RESULTS/performix/run-ids.tsv"
  "$APX_ROOT/apx" run info "$run_id" --json > "$RESULTS/performix/runs/${stem}.info.json"
  "$APX_ROOT/apx" run logs "$run_id" > "$RESULTS/performix/runs/${stem}.log.txt"
  "$APX_ROOT/apx" run prepare-render "$run_id" --json > "$RESULTS/performix/runs/${stem}.prepare-render.json"
  "$APX_ROOT/apx" run export "$run_id" "$RESULTS/performix/exports" --json \
    > "$RESULTS/performix/runs/${stem}.export.json"
}

run_profile disabled "$DISABLED"
run_profile enabled "$ENABLED"
DISABLED_RUN_ID=$(awk '$2 == "disabled" {print $3}' "$RESULTS/performix/run-ids.tsv")
ENABLED_RUN_ID=$(awk '$2 == "enabled" {print $3}' "$RESULTS/performix/run-ids.tsv")
"$ROOT/venv/bin/python" scripts/analyze_performix_execution.py \
  --disabled "$RESULTS/performix/exports/$DISABLED_RUN_ID.zip" \
  --enabled "$RESULTS/performix/exports/$ENABLED_RUN_ID.zip" \
  --minimum-enabled-share 0.50 --minimum-total-samples 100000 \
  --output "$RESULTS/performix-confirmation.json"
cp "$ROOT/variants/kleidiai-disabled/genai_config.json" "$RESULTS/disabled-genai-config.json"
cp "$ROOT/variants/kleidiai-enabled/genai_config.json" "$RESULTS/enabled-genai-config.json"
date --iso-8601=seconds > "$RESULTS/completed-at.txt"
