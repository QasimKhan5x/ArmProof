from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ActionPackageTests(unittest.TestCase):
    def test_action_is_composite_and_fail_closed(self) -> None:
        action = (ROOT / "action.yml").read_text(encoding="utf-8")
        self.assertIn("using: composite", action)
        self.assertIn('armproof ci "$ARMPROOF_CONFIG"', action)
        self.assertIn('exit "$gate_status"', action)
        self.assertIn("$GITHUB_ACTION_PATH", action)
        self.assertNotIn("pull_request_target", action)

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


if __name__ == "__main__":
    unittest.main()
