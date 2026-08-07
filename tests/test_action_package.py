from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ActionPackageTests(unittest.TestCase):
    def test_repository_ci_exercises_the_composite_action(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("action-smoke:", workflow)
        self.assertIn("uses: ./", workflow)
        self.assertIn("Confirm composite Action outputs", workflow)

    def test_pages_waits_for_current_successful_main_ci(self) -> None:
        workflow = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_run:", workflow)
        self.assertIn("workflow_run.conclusion == 'success'", workflow)
        self.assertIn("workflow_run.event == 'push'", workflow)
        self.assertIn(
            "workflow_run.head_repository.full_name == github.repository", workflow
        )
        self.assertIn("git rev-parse origin/main", workflow)
        self.assertIn("git diff --exit-code -- report surgedesk/data.json", workflow)
        self.assertIn("cancel-in-progress: false", workflow)

    def test_readme_installs_browser_system_dependencies(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("npx playwright install --with-deps chromium", readme)

    def test_release_attestation_recomputes_outside_the_checkout(self) -> None:
        workflow = (ROOT / ".github/workflows/evidence-attestation.yml").read_text(
            encoding="utf-8"
        )
        for experiment in ("EXP-2026-015", "EXP-2026-016", "EXP-2026-017"):
            self.assertIn(f"ops/evidence/{experiment}/evidence.tar.gz", workflow)
        self.assertIn("build/preregistration.bundle", workflow)
        self.assertIn('repository="$RUNNER_TEMP/armproof-recompute"', workflow)
        self.assertIn('git_commit_verified_in_checkout', workflow)
        self.assertIn("Require successful CI for this exact commit", workflow)
        self.assertIn('gh release create "$GITHUB_REF_NAME"', workflow)
        self.assertNotIn("release:\n    types: [published]", workflow)

    def test_action_is_composite_and_fail_closed(self) -> None:
        action = (ROOT / "action.yml").read_text(encoding="utf-8")
        self.assertIn("using: composite", action)
        self.assertIn('armproof ci "$ARMPROOF_CONFIG"', action)
        self.assertIn('--contract-sha256 "$ARMPROOF_CONTRACT_SHA256"', action)
        self.assertIn("required: true", action)
        self.assertIn('exit "$gate_status"', action)
        self.assertIn("$GITHUB_ACTION_PATH", action)
        self.assertIn('python3.12 -m pip install "$GITHUB_ACTION_PATH"', action)
        self.assertIn(
            'python3.12 "$GITHUB_ACTION_PATH/scripts/write_github_summary.py"',
            action,
        )
        self.assertNotIn('run: python -m pip install "$GITHUB_ACTION_PATH"', action)
        self.assertNotIn("pull_request_target", action)

    def test_generic_quickstart_uses_the_adopters_contract_digest(self) -> None:
        quickstart = (ROOT / "docs/QUICKSTART.md").read_text(encoding="utf-8")
        self.assertIn("sha256sum contract.json", quickstart)
        self.assertIn("REPLACE_WITH_RELEASE_COMMIT_SHA", quickstart)
        self.assertIn("REPLACE_WITH_CONTRACT_SHA256", quickstart)
        self.assertIn(
            "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
            quickstart,
        )
        self.assertNotIn(
            "contract-sha256: 5233b0cb7898a02f451de51f1cf43a15829dda07306dd71ddfafbc1311f47369",
            quickstart,
        )

    def test_job_summary_renderer_handles_unknown_claim(self) -> None:
        decision = ROOT / "build" / "test-action-decision.json"
        decision.parent.mkdir(parents=True, exist_ok=True)
        decision.write_text(json.dumps({
            "schema_version": "1.0.0",
            "passed": False,
            "claims": [{
                "claim_id": "arm|path",
                "status": "unknown",
                "reason_code": "attribution_missing",
                "observed": None,
                "threshold": 1.0,
            }],
        }), encoding="utf-8")
        result = subprocess.run(
            ["python3.12", str(ROOT / "scripts" / "write_github_summary.py"), str(decision)],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("ArmProof: blocked", result.stdout)
        self.assertIn("arm\\|path", result.stdout)
        self.assertIn("unknown", result.stdout)

    def test_job_summary_includes_runtime_release_conditions(self) -> None:
        decision = ROOT / "build" / "test-action-passed.json"
        summary = ROOT / "build" / "test-action-summary.json"
        decision.parent.mkdir(parents=True, exist_ok=True)
        decision.write_text(json.dumps({
            "schema_version": "1.0.0", "passed": True, "claims": [],
        }), encoding="utf-8")
        summary.write_text(json.dumps({
            "runtime_memory": {
                "passed": True,
                "sustained_experiment_id": "EXP-2026-015",
                "isolation_experiment_id": "EXP-2026-016",
                "simplification_experiment_id": "EXP-2026-017",
                "candidate_rps": 0.62,
                "confirmation_passes": 5,
                "confirmation_windows": 5,
                "p95_reduction_percent": 44.977,
                "raw_output_rows": 2790,
                "raw_output_cases": 186,
                "complete_raw_rows": 3678,
                "complete_raw_windows": 31,
            },
        }), encoding="utf-8")
        result = subprocess.run(
            [
                "python3.12", str(ROOT / "scripts" / "write_github_summary.py"),
                str(decision), str(summary),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("Sustained Graviton runtime checks", result.stdout)
        self.assertIn("EXP-2026-015", result.stdout)
        self.assertIn("2,790 raw responses", result.stdout)
        self.assertIn("3,678 rows across 31 windows", result.stdout)


if __name__ == "__main__":
    unittest.main()
