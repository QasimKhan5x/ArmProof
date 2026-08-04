#!/usr/bin/env bash
set -Eeuo pipefail

[[ "${EXPERIMENT_APPROVAL_TOKEN:-}" == "exp-2026-013-performix-confirmation" ]] || exit 64

export HOME=/root
ROOT=/opt/armproof
WORK="$ROOT/work"
RESULTS="$ROOT/evidence"
APX_ROOT="$ROOT/performix"
mkdir -p "$WORK" "$RESULTS" "$APX_ROOT"
exec > >(tee -a "$RESULTS/guest.log") 2>&1

upload_results() {
  status=$?
  set +e
  printf '%s\n' "$status" > "$RESULTS/exit-status.txt"
  date --iso-8601=seconds > "$RESULTS/finished-at.txt"
  "$APX_ROOT/apx" run list --json > "$RESULTS/performix/run-list-final.json" 2>&1 || true
  find "$RESULTS" -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > "$RESULTS/SHA256SUMS"
  tar -C "$ROOT" -czf /tmp/armproof-performix-evidence.tar.gz evidence
  curl -fsS -X PUT -T /tmp/armproof-performix-evidence.tar.gz "$RESULT_UPLOAD_URL"
  shutdown -h now
}
trap upload_results EXIT

shutdown -h +45
curl -fsSL "$PROJECT_BUNDLE_URL" -o /tmp/project.tar.gz
echo "$PROJECT_BUNDLE_SHA256  /tmp/project.tar.gz" | sha256sum -c -
printf '%s  /tmp/project.tar.gz\n' "$PROJECT_BUNDLE_SHA256" > "$RESULTS/project-bundle.sha256"
tar -xzf /tmp/project.tar.gz -C "$WORK"
cd "$WORK"
source ops/aws/performix-003/workload.sh
