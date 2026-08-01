from __future__ import annotations

import tarfile
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from armproof.cloud.aws import assert_approved, make_plan
from armproof.cloud.runner import make_project_bundle, render_user_data, terminate_and_wait


class AwsPlanTests(unittest.TestCase):
    def test_plan_is_immutable_budgeted_and_armproof_tagged(self) -> None:
        plan = make_plan(
            "EXP-CAP-001", now=datetime(2026, 7, 31, tzinfo=UTC),
            maximum_runtime_minutes=120, prior_spend_usd=1.43,
        )
        self.assertEqual(plan.tags["Project"], "ArmProof")
        self.assertLess(plan.maximum_projected_total_usd, 15)
        self.assertEqual(len(plan.approval_token()), 16)
        assert_approved(plan, plan.approval_token())
        with self.assertRaises(PermissionError):
            assert_approved(plan, "wrong")

    def test_cumulative_ceiling_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "cumulative"):
            make_plan("EXP-CAP-001", prior_spend_usd=14.9)

    def test_termination_handles_stopping(self) -> None:
        class Ec2:
            def __init__(self) -> None:
                self.states = iter(["stopping", "shutting-down", "terminated"])
                self.calls = 0

            def terminate_instances(self, **_: object) -> None:
                self.calls += 1

            def describe_instances(self, **_: object) -> dict:
                return {"Reservations": [{"Instances": [{"State": {"Name": next(self.states)}}]}]}

        ec2 = Ec2()
        terminate_and_wait(ec2, "i-test", poll_seconds=0, timeout_seconds=1)
        self.assertEqual(ec2.calls, 1)

    def test_bundle_excludes_secrets_models_git_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src/app.py").write_text("pass")
            (root / ".git").mkdir()
            (root / ".git/config").write_text("secret")
            (root / "models").mkdir()
            (root / "models/model.bin").write_text("large")
            (root / "node_modules").mkdir()
            (root / "node_modules/dependency.js").write_text("vendor")
            (root / ".env").write_text("TOKEN=secret")
            (root / "ops/evidence").mkdir(parents=True)
            (root / "ops/evidence/raw").write_text("old")
            (root / "ops/aws").mkdir(parents=True)
            (root / "ops/aws/protocol.json").write_text("{}")
            destination = root / "bundle.tar.gz"
            self.assertEqual(len(make_project_bundle(root, destination)), 64)
            with tarfile.open(destination) as archive:
                names = archive.getnames()
            self.assertIn("src/app.py", names)
            self.assertNotIn(".git/config", names)
            self.assertNotIn("models/model.bin", names)
            self.assertNotIn("node_modules/dependency.js", names)
            self.assertNotIn("ops/evidence/raw", names)
            self.assertIn("ops/aws/protocol.json", names)
            self.assertNotIn(".env", names)

    def test_user_data_rejects_injection_and_large_payloads(self) -> None:
        rendered = render_user_data(
            "#!/usr/bin/env bash\ntrue\n", project_url="https://example.test/p",
            project_sha256="a" * 64, result_url="https://example.test/r",
            experiment_token="token", extra_exports={"ASSET_URL": "https://example.test/a"},
        )
        self.assertEqual(rendered.count("#!/usr/bin/env bash"), 1)
        with self.assertRaisesRegex(ValueError, "unsafe"):
            render_user_data(
                "true\n", project_url="bad\ncommand", project_sha256="a" * 64,
                result_url="url", experiment_token="token",
            )


if __name__ == "__main__":
    unittest.main()
