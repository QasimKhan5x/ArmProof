from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class PublicClaimConsistencyTests(unittest.TestCase):
    def test_ui_derives_measured_values_from_evidence(self) -> None:
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

    def test_readme_leads_with_product_and_arm_optimization(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        first_section = readme[:3000]
        self.assertIn("SurgeDesk", first_section)
        self.assertIn("ArmProof", first_section)
        self.assertIn("KleidiAI", first_section)
        self.assertIn("Graviton4", first_section)
        self.assertNotIn("benchmark dashboard", first_section.lower())

    def test_live_flow_uses_real_gateway_routes(self) -> None:
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

    def test_identity_incomplete_confirmation_remains_rejected(self) -> None:
        result = (ROOT / "ops/evidence/EXP-2026-012/RESULT.md").read_text(
            encoding="utf-8"
        )
        self.assertTrue(result.startswith("# EXP-2026-012 Result: Rejected"))
        self.assertIn("source_artifact_sha256", result)
        self.assertIn("No result from EXP-2026-012", result)


if __name__ == "__main__":
    unittest.main()
