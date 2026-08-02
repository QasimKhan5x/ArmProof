"""Live SurgeDesk routing composition around the pinned inference contract."""

from __future__ import annotations

from typing import Any

from armproof.demo.queue_guard import QueueGuard, queue_for_intent
from armproof.demo.surgedesk import HIGH_PRIORITY, _friendly, _procedure
from armproof.quality.banking77 import _parse_intent


def build_prompt(text: str, categories: list[str]) -> str:
    labels = ", ".join(categories)
    return (
        "Route this online-banking support request.\n"
        f"Valid intent labels: {labels}\n"
        'Return only JSON in this form: {"intent":"one_valid_label"}.\n'
        f"Customer request: {text}"
    )


def compose_live_route(
    text: str,
    upstream: dict[str, Any],
    guard: QueueGuard,
    categories: list[str],
) -> dict[str, Any]:
    intent, schema_valid, error = _parse_intent(upstream.get("output"), set(categories))
    prediction = guard.predict(text)
    llm_queue = queue_for_intent(intent)
    return {
        "request_id": upstream.get("request_id", "live-request"),
        "source_text": text,
        "suggested_intent": intent,
        "suggested_label": _friendly(intent),
        "llm_queue": llm_queue,
        "guard_queue": prediction.queue,
        "queue": prediction.queue,
        "guard_overrode": prediction.queue != llm_queue,
        "guard_margin": prediction.margin,
        "priority": "Urgent" if intent in HIGH_PRIORITY else "Standard",
        "suggested_procedure": _procedure(intent),
        "expected_procedure": None,
        "schema_valid": schema_valid,
        "parse_error": error,
        "queue_correct": None,
        "correct": None,
        "mode": "live_model_output",
        "backend": upstream.get("backend", "unknown"),
        "inference_ms": upstream.get("inference_ms"),
    }
