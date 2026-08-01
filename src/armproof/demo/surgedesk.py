"""Build the SurgeDesk demo exclusively from versioned ArmProof evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEMO_CASE_IDS = (
    "banking77-quality-0110",
    "banking77-quality-0355",
    "banking77-quality-0279",
    "banking77-quality-0211",
    "banking77-quality-0056",
    "banking77-quality-0001",
)

HIGH_PRIORITY = {
    "lost_or_stolen_card",
    "compromised_card",
    "card_payment_not_recognised",
    "cash_withdrawal_not_recognised",
    "direct_debit_payment_not_recognised",
    "lost_or_stolen_phone",
}

PROCEDURES = {
    "lost_or_stolen_card": "Verify the customer, freeze the card, and start replacement-card intake.",
    "compromised_card": "Escalate to account security and review recent access before restoring service.",
    "card_payment_not_recognised": "Secure the card and open a card-payment dispute for human review.",
    "transfer_not_received_by_recipient": "Collect the transfer reference and trace recipient settlement status.",
    "pending_cash_withdrawal": "Check the ATM settlement window and prevent duplicate reimbursement.",
    "card_delivery_estimate": "Confirm the delivery region and provide the latest dispatch estimate.",
    "card_arrival": "Check card dispatch status and confirm the delivery address.",
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _friendly(intent: str | None) -> str:
    return "Needs human review" if intent is None else intent.replace("?", "").replace("_", " ").title()


def _queue(intent: str | None) -> str:
    if intent is None:
        return "Manual review"
    if intent in HIGH_PRIORITY:
        return "Account security"
    if "cash_withdrawal" in intent or intent in {"atm_support", "cash_withdrawal_charge", "card_swallowed"}:
        return "Cash & ATM"
    if "transfer" in intent or intent in {"beneficiary_not_allowed", "receiving_money"}:
        return "Transfers"
    if "card" in intent:
        return "Cards & payments"
    return "Account support"


def _procedure(intent: str | None) -> str:
    if intent is None:
        return "Inspect the request and choose a queue before contacting the customer."
    return PROCEDURES.get(intent, f"Review the { _friendly(intent).lower() } playbook before responding.")


def _extract_customer_text(prompt: str) -> str:
    marker = "Customer request: "
    if marker not in prompt:
        raise ValueError("BANKING77 prompt is missing customer request marker")
    return prompt.rsplit(marker, 1)[1]


def _event_rows(path: Path, workload: dict[str, str]) -> list[dict[str, Any]]:
    result = []
    for index, row in enumerate(_load_jsonl(path)):
        response = row.get("response") or {}
        request_id = response.get("request_id")
        if request_id not in workload:
            raise ValueError(f"replay request is absent from frozen workload: {request_id}")
        result.append(
            {
                "sequence": index + 1,
                "request_id": request_id,
                "source_text": workload[request_id],
                "latency_ms": row["latency_ms"],
                "queue_ms": response.get("queue_ms", 0.0),
                "within_slo": row["latency_ms"] <= 10_000,
                "status_code": row["status_code"],
            }
        )
    return result


def build_surgedesk_payload(root: Path) -> dict[str, Any]:
    evidence = root / "ops/evidence/EXP-2026-004/accepted/evidence/capacity/experiment"
    summary = _load_json(evidence / "summary.json")
    confirmations = _load_json(evidence / "confirmations.json")
    quality_enabled = _load_json(evidence / "quality/kleidiai-enabled.json")
    quality_disabled = _load_json(evidence / "quality/kleidiai-disabled.json")
    quality_cases = {
        row["request_id"]: row
        for row in _load_jsonl(root / "data/banking77/generated/quality.jsonl")
    }
    quality_rows = {row["request_id"]: row for row in quality_enabled["rows"]}

    routing_cases = []
    for request_id in DEMO_CASE_IDS:
        case = quality_cases[request_id]
        observed = quality_rows[request_id]
        suggested = observed["predicted_intent"]
        expected = observed["expected_intent"]
        routing_cases.append(
            {
                "request_id": request_id,
                "source_text": case["source_text"],
                "suggested_intent": suggested,
                "suggested_label": _friendly(suggested),
                "expected_intent": expected,
                "expected_label": _friendly(expected),
                "queue": _queue(suggested),
                "expected_queue": _queue(expected),
                "priority": "Urgent" if expected in HIGH_PRIORITY else "Standard",
                "procedure": _procedure(expected),
                "correct": observed["correct"],
                "mode": "recorded_model_output",
            }
        )

    mixed_workload = {
        row["request_id"]: _extract_customer_text(row["payload"]["prompt"])
        for row in _load_jsonl(root / "data/banking77/generated/traffic-mixed.jsonl")
    }
    baseline_path = evidence / (
        "capacity/mixed/kleidiai-disabled/confirmations/rep-1-fail.jsonl"
    )
    optimized_path = evidence / (
        "capacity/mixed/kleidiai-enabled/confirmations/rep-1-pass.jsonl"
    )
    baseline_confirmation = confirmations["mixed"]["kleidiai-disabled"][0]["fail"]
    optimized_confirmation = confirmations["mixed"]["kleidiai-enabled"][0]["pass"]

    deployment = _load_json(root / "ops/evidence/result-first/EXP-2026-002/summary.json")["summary"]
    comparison = _load_json(root / "examples/armproof-reference/comparison.json")
    reproduction = _load_json(root / "ops/evidence/EXP-2026-005/reproduction-comparison.json")
    observed_reproduction_difference = max(
        mix["relative_difference"] for mix in reproduction["mixes"].values()
    )

    mixes = {}
    for name, result in summary["mixes"].items():
        mixes[name] = {
            "baseline_sustainable_rps": result["ratio"]["baseline_median"],
            "optimized_sustainable_rps": result["ratio"]["treatment_median"],
            "ratio": round(result["ratio"]["ratio"], 6),
            "confirmations_per_treatment": result["ratio"]["baseline_samples"],
        }

    return {
        "schema_version": "1.0.0",
        "product": {
            "name": "SurgeDesk",
            "description": "Human-confirmed support triage on an Arm-optimized cloud AI service.",
            "demo_mode": "recorded_evidence_replay",
        },
        "routing_cases": routing_cases,
        "capacity": {"slo_ms": 10_000, "mixes": mixes},
        "quality": {
            "baseline_accuracy_percent": quality_disabled["accuracy"] * 100,
            "optimized_accuracy_percent": quality_enabled["accuracy"] * 100,
            "accuracy_delta_pp": summary["quality_comparison"]["accuracy_delta_pp"],
            "macro_f1_delta_pp": summary["quality_comparison"]["macro_f1_delta_pp"],
            "schema_valid_percent": summary["quality_comparison"]["schema_valid_rate"] * 100,
            "evaluated_cases": quality_enabled["total"],
            "human_confirmation_required": True,
            "claim_boundary": "Quality is non-inferior between treatments; absolute accuracy is not production-ready for autonomous routing.",
        },
        "replay": {
            "baseline": {
                "label": "KleidiAI disabled",
                "offered_rps": baseline_confirmation["offered_rps"],
                "p95_ms": baseline_confirmation["summary"]["p95_ms"],
                "passed": baseline_confirmation["passed"],
                "events": _event_rows(baseline_path, mixed_workload),
            },
            "optimized": {
                "label": "KleidiAI enabled",
                "offered_rps": optimized_confirmation["offered_rps"],
                "p95_ms": optimized_confirmation["summary"]["p95_ms"],
                "passed": optimized_confirmation["passed"],
                "events": _event_rows(optimized_path, mixed_workload),
            },
        },
        "proof": {
            "decision": "PASS",
            "instance": comparison["treatment"]["controls"]["instance"],
            "threads": comparison["treatment"]["controls"]["threads"],
            "kleidiai_enabled_callchains": comparison["arm_attribution"]["treatment_observed"],
            "kleidiai_disabled_callchains": comparison["arm_attribution"]["baseline_observed"],
            "artifact_reduction_percent": deployment["disk_reduction_percent"],
            "peak_pss_reduction_percent": deployment["peak_pss_reduction_percent"],
            "weighted_pss_reduction_percent": deployment["weighted_pss_reduction_percent"],
            "direct_speedup_min": min(deployment["kleidiai_shape_gains"]),
            "direct_speedup_max": max(deployment["kleidiai_shape_gains"]),
            "reproduction_max_relative_difference_percent": observed_reproduction_difference * 100,
            "reproduction_experiment_id": "EXP-2026-005",
        },
        "provenance": {
            "experiment_id": "EXP-2026-004",
            "dataset": "BANKING77",
            "dataset_license": "CC-BY-4.0",
            "model": "Phi-4 Mini",
            "runtime": "ONNX Runtime GenAI INT4 + KleidiAI",
            "machine": "AWS Graviton4 c8g.4xlarge",
            "report_path": "../report/index.html",
            "release_url": "https://github.com/QasimKhan5x/VerifyLane/releases/tag/v0.1.0",
        },
    }
