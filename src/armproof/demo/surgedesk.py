"""Build the SurgeDesk demo exclusively from versioned ArmProof evidence."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from armproof.contracts import parse_contract
from armproof.demo.queue_guard import QueueGuard, queue_for_intent
from armproof.evidence import comparison_to_dict, verify_and_derive
from armproof.evidence.sustained_audit import derive_sustained_audit
from armproof.policy import decision_to_dict


DEMO_CASE_IDS = (
    "banking77-quality-0110",
    "banking77-quality-0007",
    "banking77-quality-0355",
    "banking77-quality-0279",
    "banking77-quality-0211",
    "banking77-quality-0056",
    "banking77-quality-0044",
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


def _procedure(intent: str | None) -> str:
    if intent is None:
        return "Inspect the request and choose a queue before contacting the customer."
    return PROCEDURES.get(intent, f"Review the { _friendly(intent).lower() } playbook before responding.")


def _extract_customer_text(prompt: str) -> str:
    marker = "Customer request: "
    if marker not in prompt:
        raise ValueError("BANKING77 prompt is missing customer request marker")
    return prompt.rsplit(marker, 1)[1]


def _claim_rows(contract: Any, decision: dict[str, Any]) -> list[dict[str, Any]]:
    labels = {
        "quality-accuracy": "Quality accuracy",
        "quality-macro-f1": "Macro F1",
        "quality-schema": "Output schema",
        "sustained-capacity-lower-bound": "Sustained capacity lower bound",
        "sustained-window-count": "Long confirmation windows",
        "sustained-request-count": "Raw request outcomes",
        "arm-execution": "Executed Arm path",
        "arm-cycle-attribution": "KleidiAI cycle attribution",
        "perf-sample-integrity": "Profiler sample integrity",
    }
    results = {row["claim_id"]: row for row in decision["claims"]}
    return [
        {
            "id": spec.claim_id,
            "label": labels[spec.claim_id],
            "metric": spec.metric,
            "operator": spec.operator,
            "observed": results[spec.claim_id]["observed"],
            "threshold": spec.threshold,
            "status": results[spec.claim_id]["status"],
        }
        for spec in contract.claims
    ]


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


def _percentile_95(rows: list[dict[str, Any]]) -> float:
    values = sorted(row["latency_ms"] for row in rows)
    return values[max(0, (95 * len(values) + 99) // 100 - 1)]


def _queue_guard(root: Path) -> tuple[QueueGuard, list[dict[str, str]]]:
    with (root / "data/banking77/source/test.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        source_rows = list(csv.DictReader(stream))
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in source_rows:
        grouped[row["category"]].append(row)
    evaluation = []
    training = []
    for rows in grouped.values():
        evaluation.extend(rows[:10])
        training.extend(rows[10:])
    guard = QueueGuard((row["text"], queue_for_intent(row["category"])) for row in training)
    return guard, evaluation


def build_surgedesk_payload(root: Path) -> dict[str, Any]:
    accepted_evidence = root / "ops/evidence/EXP-2026-004/accepted/evidence"
    sustained_contract = parse_contract(
        _load_json(root / "examples/armproof-reference/sustained-contract.json")
    )
    sustained = derive_sustained_audit(
        root / "ops/evidence/EXP-2026-009/evidence.tar.gz",
        expected_sha256="f22e647aabe40eefd2abc5548306f40e2a5558ce1a85bc31c18319e6e51d78da",
        contract=sustained_contract,
        workload_manifest=root / "data/banking77/generated/manifest.json",
    )
    contract = parse_contract(
        _load_json(root / "examples/armproof-reference/contract.json")
    )
    verified = verify_and_derive(
        contract,
        accepted_evidence,
        accepted_evidence / "SHA256SUMS",
        root / "data/banking77/generated/manifest.json",
        root / "ops/evidence/EXP-2026-005/accepted/evidence",
        root / "ops/evidence/EXP-2026-005/accepted/evidence/SHA256SUMS",
    )
    decision = decision_to_dict(sustained.decision)
    checksum_result = verified.checksums
    evidence = accepted_evidence / "capacity/experiment"
    summary = dict(verified.summary)
    quality_enabled = _load_json(evidence / "quality/kleidiai-enabled.json")
    quality_disabled = _load_json(evidence / "quality/kleidiai-disabled.json")
    quality_cases = {
        row["request_id"]: row
        for row in _load_jsonl(root / "data/banking77/generated/quality.jsonl")
    }
    quality_rows = {row["request_id"]: row for row in quality_enabled["rows"]}
    guard, guard_evaluation = _queue_guard(root)
    frozen_texts = [quality_cases[row_id]["source_text"] for row_id in quality_rows]
    if frozen_texts != [row["text"] for row in guard_evaluation]:
        raise ValueError("queue-guard evaluation does not match frozen quality set")

    llm_queue_correct = 0
    guard_queue_correct = 0
    for request_id, observed in quality_rows.items():
        source_text = quality_cases[request_id]["source_text"]
        expected_queue = queue_for_intent(observed["expected_intent"])
        llm_queue_correct += queue_for_intent(observed["predicted_intent"]) == expected_queue
        guard_queue_correct += guard.predict(source_text).queue == expected_queue

    routing_cases = []
    for request_id in DEMO_CASE_IDS:
        case = quality_cases[request_id]
        observed = quality_rows[request_id]
        suggested = observed["predicted_intent"]
        expected = observed["expected_intent"]
        guard_prediction = guard.predict(case["source_text"])
        llm_queue = queue_for_intent(suggested)
        expected_queue = queue_for_intent(expected)
        routing_cases.append(
            {
                "request_id": request_id,
                "source_text": case["source_text"],
                "suggested_intent": suggested,
                "suggested_label": _friendly(suggested),
                "expected_intent": expected,
                "expected_label": _friendly(expected),
                "llm_queue": llm_queue,
                "guard_queue": guard_prediction.queue,
                "queue": guard_prediction.queue,
                "expected_queue": expected_queue,
                "guard_overrode": guard_prediction.queue != llm_queue,
                "guard_margin": guard_prediction.margin,
                "priority": "Urgent" if expected in HIGH_PRIORITY else "Standard",
                "suggested_procedure": _procedure(suggested),
                "expected_procedure": _procedure(expected),
                "intent_correct": observed["correct"],
                "queue_correct": guard_prediction.queue == expected_queue,
                "correct": guard_prediction.queue == expected_queue,
                "mode": "recorded_model_output",
            }
        )

    mixed_workload = {
        row["request_id"]: _extract_customer_text(row["payload"]["prompt"])
        for row in _load_jsonl(root / "data/banking77/generated/traffic-mixed.jsonl")
    }
    baseline_path = evidence / (
        "capacity/mixed/kleidiai-disabled/discovery/rps-0.266667.jsonl"
    )
    optimized_path = evidence / (
        "capacity/mixed/kleidiai-enabled/discovery/rps-0.266667.jsonl"
    )
    baseline_events = _event_rows(baseline_path, mixed_workload)
    optimized_events = _event_rows(optimized_path, mixed_workload)

    deployment = _load_json(root / "ops/evidence/result-first/EXP-2026-002/summary.json")["summary"]
    comparison = comparison_to_dict(verified.comparison)
    computed_guard_accuracy = guard_queue_correct / quality_enabled["total"]
    if comparison["metrics"].get("guard_queue_accuracy") != computed_guard_accuracy:
        raise ValueError("ArmProof queue-quality claim differs from recomputed result")
    observed_reproduction_difference = summary["reproduction"][
        "maximum_relative_difference"
    ]

    mixes = {
        "mixed": {
            "baseline_sustainable_rps": sustained.baseline_pass_rps,
            "baseline_fail_rps": sustained.baseline_fail_rps,
            "optimized_sustainable_rps": sustained.treatment_pass_rps,
            "optimized_probe_rps": sustained.treatment_fail_rps,
            "tested_pass_point_ratio": sustained.tested_pass_point_ratio,
            "minimum_capacity_ratio": sustained.minimum_capacity_ratio,
            "confirmations_per_treatment": sustained.confirmations,
            "confirmation_seconds": sustained.confirmation_seconds,
            "baseline_pass_p95_ms": sustained.baseline_pass_p95_ms,
            "optimized_pass_p95_ms": sustained.treatment_pass_p95_ms,
            "optimized_probe_p95_ms": sustained.treatment_fail_probe_p95_ms,
            "optimized_probe_failures": sustained.treatment_failures_at_fail_probe,
        }
    }

    return {
        "schema_version": "1.0.0",
        "product": {
            "name": "SurgeDesk",
            "description": "Human-confirmed support triage on an Arm-optimized cloud AI service.",
            "demo_mode": "accepted_evidence_load",
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
            "llm_queue_correct": llm_queue_correct,
            "llm_queue_accuracy_percent": llm_queue_correct / quality_enabled["total"] * 100,
            "guard_queue_correct": guard_queue_correct,
            "guard_queue_accuracy_percent": guard_queue_correct / quality_enabled["total"] * 100,
            "guard_queue_gain_pp": (guard_queue_correct - llm_queue_correct)
            / quality_enabled["total"]
            * 100,
            "guard_training_cases": 2310,
            "guard_evaluation_cases": 770,
            "guard_algorithm": "Multinomial Naive Bayes with word unigrams and bigrams",
            "human_confirmation_required": True,
            "claim_boundary": "The held-out queue guard exceeds the assistive-routing target; human confirmation remains required.",
        },
        "replay": {
            "comparison": "equal_offered_load",
            "source_experiment_id": "EXP-2026-004",
            "note": "Supporting short-window raw slice at identical demand; the EXP-2026-009 sustained boundaries are reported separately.",
            "baseline": {
                "label": "KleidiAI disabled",
                "offered_rps": 0.26666666666666666,
                "p95_ms": _percentile_95(baseline_events),
                "passed": _percentile_95(baseline_events) <= 10_000,
                "events": baseline_events,
            },
            "optimized": {
                "label": "KleidiAI enabled",
                "offered_rps": 0.26666666666666666,
                "p95_ms": _percentile_95(optimized_events),
                "passed": _percentile_95(optimized_events) <= 10_000,
                "events": optimized_events,
            },
        },
        "proof": {
            "decision": "PASS" if decision["passed"] else "BLOCK",
            "decision_source": "derived_from_versioned_sustained_contract",
            "contract_id": sustained_contract.contract_id,
            "claims": _claim_rows(sustained_contract, decision),
            "verified_claims": sum(
                claim["status"] == "pass" for claim in decision["claims"]
            ),
            "instance": sustained.comparison.treatment.controls["instance"],
            "threads": sustained.comparison.treatment.controls["threads"],
            "kleidiai_enabled_callchains": sustained.comparison.arm_path_treatment_observed,
            "kleidiai_disabled_callchains": sustained.comparison.arm_path_baseline_observed,
            "kleidiai_cycle_callchain_share_percent": (
                sustained.enabled_kai_cycle_share * 100
            ),
            "artifact_reduction_percent": deployment["disk_reduction_percent"],
            "peak_pss_reduction_percent": deployment["peak_pss_reduction_percent"],
            "weighted_pss_reduction_percent": deployment["weighted_pss_reduction_percent"],
            "direct_speedup_min": min(deployment["kleidiai_shape_gains"]),
            "direct_speedup_max": max(deployment["kleidiai_shape_gains"]),
            "reproduction_max_relative_difference_percent": observed_reproduction_difference * 100,
            "reproduction_experiment_id": "EXP-2026-005",
        },
        "provenance": {
            "experiment_id": sustained.experiment_id,
            "release_experiment_id": "EXP-2026-004",
            "original_gate_passed": sustained.original_gate_passed,
            "corrected_claim_passed": sustained.corrected_claim_passed,
            "claim_boundary": (
                "The original exact 2.5x bracket gate was rejected. The public claim "
                "is the independently supported >=2.0x sustained-capacity lower bound."
            ),
            "evidence": {
                "checksum_verified": checksum_result.passed,
                "checksummed_files": checksum_result.checked,
                "reproduction_checksum_verified": verified.reproduction_checksums.passed,
                "reproduction_checksummed_files": verified.reproduction_checksums.checked,
                "sustained_archive_verified": True,
                "sustained_archive_sha256": sustained.archive_sha256,
                "sustained_internal_checksums_verified": (
                    sustained.internal_checksums_verified
                ),
                "sustained_checksummed_files": sustained.internal_checksummed_files,
                "sustained_raw_confirmation_files": sustained.raw_confirmation_files,
                "sustained_raw_confirmation_samples": sustained.raw_confirmation_samples,
                "sustained_matched_control_verified": sustained.matched_control_verified,
                "total_checksummed_files": (
                    checksum_result.checked + verified.reproduction_checksums.checked
                    + sustained.internal_checksummed_files
                ),
                "comparison": "matched_control",
                "only_changed_control": sustained.only_changed_control,
            },
            "dataset": "BANKING77",
            "dataset_license": "CC-BY-4.0",
            "model": "Phi-4 Mini",
            "runtime": "ONNX Runtime GenAI INT4 + KleidiAI",
            "machine": "AWS Graviton4 c8g.4xlarge",
            "report_path": "../report/index.html",
            "release_url": "https://github.com/QasimKhan5x/VerifyLane/releases/tag/v0.4.0",
        },
    }
