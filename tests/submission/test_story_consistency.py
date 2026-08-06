from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class SubmissionStoryTests(unittest.TestCase):
    def test_demo_is_one_ordered_live_product_flow(self) -> None:
        script = (ROOT / "submission/DEMO_SCRIPT.md").read_text(encoding="utf-8")
        moments = (
            "My card was stolen while I am travelling",
            "Compare current route with Arm candidate",
            "Recompute release decision",
            "Open confirmed result",
            "Review and switch live traffic",
            "Switch live traffic to optimized service",
            "My card is about to expire",
        )
        positions = [script.index(moment) for moment in moments]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("different message", script.lower())
        self.assertIn(
            "surgedesk is the banking-support application. armproof is its reusable",
            script.lower(),
        )
        self.assertIn("live requests:", script.lower())
        self.assertIn("evidence validation:", script.lower())
        self.assertIn("full recollection:", script.lower())
        self.assertIn("end the recording on the cutover summary", script.lower())
        self.assertNotIn("use this customer message both times", script.lower())
        self.assertNotIn("paste the same message", script.lower())
        for staged_device in (
            "2.5 times",
            "2.5x",
            "tamper",
            "checksum mismatch",
            "preloaded results",
            "pretending to rerun",
            "checksum trick",
            "activate verified optimized service",
        ):
            self.assertNotIn(staged_device, script.lower())

    def test_ui_contains_no_embedded_result_numbers_or_theatrical_timer(self) -> None:
        source = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in ("surgedesk/index.html", "surgedesk/app.mjs")
        )
        for measured_literal in (
            "EXP-2026-012",
            "0.28 r/s",
            "0.56 r/s",
            "2,100",
            "1,540",
            "67.02",
            "68.53",
            "67.35",
            "35.92",
            "55.34",
            "EXP-2026-014",
        ):
            self.assertNotIn(measured_literal, source)
        self.assertNotIn("setTimeout", source)

    def test_demo_narration_leaves_time_for_real_interactions(self) -> None:
        lines = (ROOT / "submission/DEMO_SCRIPT.md").read_text(
            encoding="utf-8"
        ).splitlines()
        narration_words = sum(
            len(line.lstrip("> ").split()) for line in lines if line.startswith(">")
        )
        self.assertLessEqual(narration_words, 320)

    def test_submission_leads_with_product_and_arm_optimization(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        devpost = (ROOT / "submission/DEVPOST_SUBMISSION.md").read_text(
            encoding="utf-8"
        )
        for document in (readme, devpost):
            first_section = document[:3000]
            self.assertIn("SurgeDesk", first_section)
            self.assertIn("ArmProof", first_section)
            self.assertIn("KleidiAI", first_section)
            self.assertIn("Graviton4", first_section)
            self.assertNotIn("benchmark dashboard", first_section.lower())

    def test_live_product_flow_uses_real_gateway_routes_in_integration_tests(self) -> None:
        browser_test = (ROOT / "tests/ui/surgedesk.spec.mjs").read_text(
            encoding="utf-8"
        )
        live_flow = browser_test.split(
            'test("public mode reveals checked-in proof', 1
        )[0].split(
            'test("a rejected optimized response refreshes', 1
        )[0]
        gateway_test = (ROOT / "tests/test_surgedesk_gateway_e2e.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("page.route(", live_flow)
        self.assertNotIn("unittest.mock", gateway_test)
        self.assertIn('receipt = _request(root, "/api/audit")', gateway_test)

    def test_identity_incomplete_confirmation_is_publicly_rejected(self) -> None:
        result = (
            ROOT / "ops/evidence/EXP-2026-012/RESULT.md"
        ).read_text(encoding="utf-8")
        self.assertTrue(result.startswith("# EXP-2026-012 Result: Rejected"))
        self.assertIn("source_artifact_sha256", result)
        self.assertIn("No result from EXP-2026-012", result)


if __name__ == "__main__":
    unittest.main()
