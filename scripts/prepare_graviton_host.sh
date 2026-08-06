#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${1:-$HOME/ArmProof}"
RUNTIME_BUNDLE="${2:-$HOME/runtime-checkpoints.tar.gz}"
VENV="${3:-$HOME/armproof-venv}"
MODELS="${4:-$HOME/armproof-models}"

cd "$ROOT"
test -f "$RUNTIME_BUNDLE"
sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv curl libmimalloc-dev
printf 'always\n' | sudo tee /sys/kernel/mm/transparent_hugepage/enabled >/dev/null
grep -q '\[always\]' /sys/kernel/mm/transparent_hugepage/enabled
ldconfig -p | grep -q 'libmimalloc\.so'
python3.12 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r ops/aws/cap-001/requirements.txt

mkdir -p "$HOME/runtime-checkpoints" "$MODELS"
tar -xzf "$RUNTIME_BUNDLE" -C "$HOME/runtime-checkpoints"
(cd "$HOME/runtime-checkpoints" && sha256sum -c SHA256SUMS)
"$VENV/bin/pip" install -q --force-reinstall --no-deps \
  "$HOME/runtime-checkpoints/onnxruntime-1.29.0-cp312-cp312-linux_aarch64.whl" \
  "$HOME/runtime-checkpoints/onnxruntime_genai-0.15.0.dev0-cp312-cp312-linux_aarch64.whl"

"$VENV/bin/hf" download microsoft/Phi-4-mini-instruct-onnx \
  --revision fc04c8f93df696602fd9f300a30d1bf2e3081347 \
  --include 'cpu_and_mobile/cpu-int4-rtn-block-32-acc-level-4/*' \
  --local-dir "$MODELS/onnx-repo"

PYTHONPATH=src "$VENV/bin/python" scripts/prepare_phi4_variants.py \
  --source "$MODELS/onnx-repo/cpu_and_mobile/cpu-int4-rtn-block-32-acc-level-4" \
  --output-root "$MODELS/variants" \
  --threads 16 \
  --replace

ARMPROOF_MODELS="$MODELS" PYTHONPATH=src "$VENV/bin/python" - <<'PY'
import json
import os
from pathlib import Path
from armproof.reference.phi4 import _ort_model_identity

root = Path(os.environ["ARMPROOF_MODELS"]) / "variants"
disabled = _ort_model_identity(root / "kleidiai-disabled")
enabled = _ort_model_identity(root / "kleidiai-enabled")
if disabled[0] != enabled[0] or disabled[1] != enabled[1]:
    raise SystemExit("matched variant identity check failed")
expected = json.loads(Path("examples/phi4-graviton/live-runtime.json").read_text())
release = json.loads(Path("surgedesk/data.json").read_text())["proof"]["live_deployment_identity"]
if disabled[1] != expected["source_artifact_sha256"]:
    raise SystemExit("downloaded model does not match the audited source artifact")
if disabled[0] != release["model_identity"]:
    raise SystemExit("prepared model fingerprint does not match the accepted audit")
if disabled[4] != expected["runtime_tuning"]["baseline"]:
    raise SystemExit("baseline runtime tuning differs from the release recipe")
if enabled[4] != expected["runtime_tuning"]["optimized"]:
    raise SystemExit("optimized runtime tuning differs from the release recipe")
print(f"READY model={disabled[0]} source={disabled[1]} threads={disabled[3]}")
PY
