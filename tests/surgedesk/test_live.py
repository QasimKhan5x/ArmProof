from __future__ import annotations

import unittest

from armproof.demo.live import build_prompt, compose_live_route
from armproof.demo.queue_guard import QueueGuard


class LiveRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.guard = QueueGuard(
            [
                ("card stolen from my wallet", "Account security"),
                ("card has not arrived", "Cards & payments"),
                ("cash machine kept my money", "Cash & ATM"),
            ]
        )
        self.categories = ["lost_or_stolen_card", "card_arrival"]

    def test_prompt_uses_bounded_intent_contract(self) -> None:
        prompt = build_prompt("My card was stolen", self.categories)
        self.assertIn("lost_or_stolen_card, card_arrival", prompt)
        self.assertTrue(prompt.endswith("Customer request: My card was stolen"))

    def test_live_route_combines_llm_intent_and_queue_guard(self) -> None:
        route = compose_live_route(
            "My card was stolen from my wallet",
            {
                "request_id": "live-1",
                "output": '{"intent":"lost_or_stolen_card"}',
                "backend": "kleidiai-enabled",
                "inference_ms": 123.0,
            },
            self.guard,
            self.categories,
        )
        self.assertEqual(route["suggested_intent"], "lost_or_stolen_card")
        self.assertEqual(route["queue"], "Account security")
        self.assertEqual(route["mode"], "live_model_output")
        self.assertEqual(route["backend"], "kleidiai-enabled")
        self.assertEqual(len(route["input_sha256"]), 64)
        self.assertEqual(len(route["model_output_sha256"]), 64)
        self.assertNotEqual(route["input_sha256"], route["model_output_sha256"])


if __name__ == "__main__":
    unittest.main()
