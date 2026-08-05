"""Build the SurgeDesk demo exclusively from versioned ArmProof evidence."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from armproof import __version__
from armproof.contracts import parse_contract
from armproof.demo.queue_guard import QueueGuard, queue_for_intent
from armproof.evidence import comparison_to_dict, get_evidence_adapter, verify_and_derive
from armproof.evidence.supporting import derive_supporting_optimization
from armproof.evidence.publication import verify_preregistration_publication


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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _friendly(intent: str | None) -> str:
    return "Needs human review" if intent is None else intent.replace("?", "").replace("_", " ").title()


def _procedure(intent: str | None) -> str:
    if intent is None:
        return "Inspect the request and choose a queue before contacting the customer."
    return PROCEDURES.get(intent, f"Review the { _friendly(intent).lower() } playbook before responding.")


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
        "raw-quality-output-count": "Raw quality outputs",
        "arm-control-zero": "KleidiAI absent in control profile",
        "arm-treatment-share": "KleidiAI share in treatment profile",
        "performix-sample-count": "Performix profile samples",
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


def _queue_guard(
    root: Path,
) -> tuple[QueueGuard, list[dict[str, str]], list[dict[str, str]]]:
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
    return guard, evaluation, training


def build_surgedesk_payload(
    root: Path,
    on_audit_stage: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    reference_config = _load_json(
        root / "examples/armproof-reference/armproof.json"
    )
    confirmation_plan = _load_json(
        root / "examples/armproof-reference" / reference_config["evidence"]["preregistration"]
    )
    application_evidence = root / "ops/evidence/EXP-2026-004/accepted/evidence"
    confirmed_contract = parse_contract(
        _load_json(
            root / "examples/armproof-reference" / reference_config["contract"]
        )
    )
    release_adapter = get_evidence_adapter(reference_config["evidence"]["adapter"])
    if on_audit_stage is None:
        release = release_adapter.verify(
            confirmed_contract,
            reference_config["evidence"],
            root / "examples/armproof-reference",
        )
    else:
        release = release_adapter.verify(
            confirmed_contract,
            reference_config["evidence"],
            root / "examples/armproof-reference",
            on_stage=on_audit_stage,
        )
    release_summary = dict(release.summary)
    performix = dict(release.performix or {})
    publication_config = reference_config.get("publication_proof")
    if not isinstance(publication_config, dict):
        raise ValueError("reference release has no preregistration publication proof")
    reference_base = root / "examples/armproof-reference"
    publication = verify_preregistration_publication(
        reference_base / publication_config["record"],
        preregistration_path=(
            reference_base / reference_config["evidence"]["preregistration"]
        ),
        project_bundle_path=(
            reference_base / publication_config["project_bundle"]
        ),
        evidence_archive_path=(
            reference_base / reference_config["evidence"]["archive"]
        ),
        expected_evidence_archive_sha256=reference_config["evidence"][
            "archive_sha256"
        ],
        repository_path=root,
    )
    discovery_config = _load_json(
        root / "examples/armproof-reference/discovery-evidence.json"
    )
    discovery_contract = parse_contract(
        _load_json(
            root / "examples/armproof-reference" / discovery_config["contract"]
        )
    )
    discovery = get_evidence_adapter(
        discovery_config["evidence"]["adapter"]
    ).verify(
        discovery_contract,
        discovery_config["evidence"],
        root / "examples/armproof-reference",
    )
    contract = parse_contract(
        _load_json(root / "examples/armproof-reference/contract.json")
    )
    migration_verified = verify_and_derive(
        contract,
        application_evidence,
        application_evidence / "SHA256SUMS",
        root / "data/banking77/generated/manifest.json",
        root / "ops/evidence/EXP-2026-005/accepted/evidence",
        root / "ops/evidence/EXP-2026-005/accepted/evidence/SHA256SUMS",
    )
    decision = release_summary["decision"]
    checksum_result = migration_verified.checksums
    evidence = application_evidence / "capacity/experiment"
    summary = dict(migration_verified.summary)
    quality_enabled = _load_json(evidence / "quality/kleidiai-enabled.json")
    quality_disabled = _load_json(evidence / "quality/kleidiai-disabled.json")
    quality_cases = {
        row["request_id"]: row
        for row in _load_jsonl(root / "data/banking77/generated/quality.jsonl")
    }
    quality_rows = {row["request_id"]: row for row in quality_enabled["rows"]}
    guard, guard_evaluation, guard_training = _queue_guard(root)
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

    scenario_roles = {
        "straight-through": next(
            row["request_id"]
            for row in routing_cases
            if row["queue_correct"] and not row["guard_overrode"]
        ),
        "guard-intervention": next(
            row["request_id"]
            for row in routing_cases
            if row["queue_correct"] and row["guard_overrode"]
        ),
        "human-correction": next(
            row["request_id"] for row in routing_cases if not row["queue_correct"]
        ),
    }
    role_by_request = {request_id: role for role, request_id in scenario_roles.items()}
    for row in routing_cases:
        row["scenario_role"] = role_by_request.get(row["request_id"])

    deployment = derive_supporting_optimization(
        root / "ops/evidence/result-first/EXP-2026-002",
        root / "examples/armproof-reference/supporting-evidence-lock.json",
    )
    application_experiment = _load_json(application_evidence / "experiment.json")
    reproduction_evidence = root / "ops/evidence/EXP-2026-005/accepted/evidence"
    reproduction_experiment = _load_json(reproduction_evidence / "experiment.json")
    runtime_lock = _load_json(root / "examples/phi4-graviton/runtime-lock.json")
    live_runtime = _load_json(root / "examples/phi4-graviton/live-runtime.json")
    if live_runtime["runtime_lock_sha256"] != _sha256(
        root / "examples/phi4-graviton/runtime-lock.json"
    ):
        raise ValueError("live runtime identity is not bound to the release lock")
    if live_runtime["source_artifact_sha256"] != release.comparison.treatment.artifact_sha256:
        raise ValueError("live runtime model identity is not bound to the release")
    model_id = runtime_lock["model_int4"]["id"]
    model_name = (
        model_id.rsplit("/", 1)[-1]
        .replace("-instruct-onnx", "")
        .replace("-mini", " Mini")
    )
    runtime_name = "ONNX Runtime GenAI INT4"
    comparison = comparison_to_dict(migration_verified.comparison)
    computed_guard_accuracy = guard_queue_correct / quality_enabled["total"]
    if comparison["metrics"].get("guard_queue_accuracy") != computed_guard_accuracy:
        raise ValueError("ArmProof queue-quality claim differs from recomputed result")
    observed_reproduction_difference = summary["reproduction"][
        "maximum_relative_difference"
    ]

    confirmed_mix = release_summary["mixes"]["mixed"]
    mixes = {
        "mixed": {
            "baseline_fail_rps": confirmed_mix["ratio"]["baseline_median"],
            "optimized_sustainable_rps": confirmed_mix["ratio"]["treatment_median"],
            "minimum_capacity_ratio": confirmed_mix["ratio"]["ratio"],
            "confirmations_per_treatment": len(
                release_summary["trial_matrix"][0]["outcomes"]
            ),
            "confirmation_seconds": release_summary["confirmation_seconds"],
            "baseline_fail_p95_ms": release_summary["trial_matrix"][0]["p95_ms"],
            "optimized_pass_p95_ms": release_summary["trial_matrix"][1]["p95_ms"],
            "trial_matrix": release_summary["trial_matrix"],
        }
    }

    release_url = f"https://github.com/QasimKhan5x/ArmProof/releases/tag/v{__version__}"
    release_tag = release_url.rsplit("/", 1)[-1]

    confirmation_windows = sum(
        len(trial["outcomes"]) for trial in release_summary["trial_matrix"]
    )
    confirmation_seconds = release_summary["confirmation_seconds"]

    payload = {
        "schema_version": "1.0.0",
        "product": {
            "name": "SurgeDesk",
            "description": "Human-confirmed support triage on an Arm-optimized cloud AI service.",
            "demo_mode": "live_gateway_with_verified_release_evidence",
        },
        "routing_cases": routing_cases,
        "capacity": {
            "slo_ms": float(confirmation_plan["acceptance"]["maximum_p95_ms"]),
            "mixes": mixes,
            "rate_selection": {
                "experiment_id": discovery.summary["experiment_id"],
                "confirmation_experiment_id": confirmation_plan["experiment_id"],
                "publication": publication,
                "trial_matrix": discovery.summary["trial_matrix"],
                "interpretation": (
                    "Discovery located the one-sided capacity bounds. The Git object for "
                    f"{confirmation_plan['experiment_id']} contains the exact final plan "
                    "and its commit time precedes the launch time recorded in experiment "
                    "metadata. It froze both rates, "
                    f"{confirmation_windows} windows of {confirmation_seconds} seconds each, "
                    "and every pass rule used here."
                ),
            },
        },
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
            "guard_training_cases": len(guard_training),
            "guard_evaluation_cases": len(guard_evaluation),
            "intent_count": len(
                {row["category"] for row in [*guard_training, *guard_evaluation]}
            ),
            "guard_algorithm": "Multinomial Naive Bayes with word unigrams and bigrams",
            "human_confirmation_required": True,
            "claim_boundary": "The held-out queue guard exceeds the assistive-routing target; human confirmation remains required.",
        },
        "proof": {
            "decision": "PASS" if decision["passed"] else "BLOCK",
            "decision_source": "derived_from_preregistered_confirmation",
            "adapter_id": release.adapter,
            "contract_id": confirmed_contract.contract_id,
            "claims": _claim_rows(confirmed_contract, decision),
            "verified_claims": sum(
                claim["status"] == "pass" for claim in decision["claims"]
            ),
            "instance": release.comparison.treatment.controls["instance"],
            "threads": release.comparison.treatment.controls["threads"],
            "live_deployment_identity": live_runtime,
            "kleidiai_enabled_callchains": release.comparison.arm_path_treatment_observed,
            "kleidiai_disabled_callchains": release.comparison.arm_path_baseline_observed,
            "kleidiai_cycle_callchain_share_percent": (
                release_summary["arm_attribution"][
                    "linux_perf_enabled_kai_cycle_share"
                ] * 100
            ),
            "artifact_reduction_percent": deployment["disk_reduction_percent"],
            "peak_pss_reduction_percent": deployment["peak_pss_reduction_percent"],
            "weighted_pss_reduction_percent": deployment["weighted_pss_reduction_percent"],
            "migration_bf16_quality_correct": deployment["migration_bf16_quality_correct"],
            "migration_int4_quality_correct": deployment["migration_int4_quality_correct"],
            "migration_quality_total": deployment["migration_quality_total"],
            "migration_quality_delta_pp": (
                deployment["migration_int4_quality_correct"]
                - deployment["migration_bf16_quality_correct"]
            ) / deployment["migration_quality_total"] * 100,
            "direct_speedup_min": min(deployment["direct_shape_gains"]),
            "direct_speedup_max": max(deployment["direct_shape_gains"]),
            "direct_shape_gains": deployment["direct_shape_gains"],
            "reproduction_max_relative_difference_percent": observed_reproduction_difference * 100,
            "reproduction_experiment_id": reproduction_experiment["experiment_id"],
            "performix": {
                "experiment_id": performix["experiment_id"],
                "scope_note": (
                    "ArmProof re-derived this matched Code Hotspots pair from "
                    "native Performix exports. Linux perf supplies separate "
                    "cycle-attribution evidence with a different denominator."
                ),
                "engine_version": performix["enabled"]["engine_version"],
                "cpu": performix["enabled"]["cpu_names"][0],
                "disabled_kai_sample_share_percent": (
                    performix["disabled"]["kai_sample_share"] * 100
                ),
                "enabled_kai_sample_share_percent": (
                    performix["enabled"]["kai_sample_share"] * 100
                ),
                "linux_perf_cycle_share_percent": release_summary[
                    "arm_attribution"
                ]["linux_perf_enabled_kai_cycle_share"] * 100,
                "enabled_function_samples": performix["enabled"][
                    "total_function_samples"
                ],
                "kernel_family": next(
                    symbol
                    for symbol in performix["enabled"]["kai_symbols"]
                    if symbol.startswith("kai_kernel_matmul")
                ),
                "internal_checksummed_files": performix["internal_checksums"][
                    "checked"
                ],
                "pmu_capability_note": (
                    f"Code Hotspots was available on the "
                    f"{release.comparison.treatment.controls['instance']} virtual PMU; "
                    "counter-heavy recipes were capability-gated and excluded."
                ),
            },
        },
        "provenance": {
            "experiment_id": release_summary["experiment_id"],
            "release_experiment_id": release_summary["experiment_id"],
            "application_evaluation_experiment_id": application_experiment[
                "experiment_id"
            ],
            "claim_boundary": {
                "released_lower_ratio": release_summary["minimum_capacity_ratio"],
                "released_lower_formula": (
                    f"{mixes['mixed']['optimized_sustainable_rps']:.2f} / "
                    f"{mixes['mixed']['baseline_fail_rps']:.2f}"
                ),
                "preregistration_publication": publication,
            },
            "evidence": {
                "checksum_verified": checksum_result.passed,
                "checksummed_files": checksum_result.checked,
                "reproduction_checksum_verified": migration_verified.reproduction_checksums.passed,
                "reproduction_checksummed_files": migration_verified.reproduction_checksums.checked,
                "sustained_archive_verified": True,
                "sustained_archive_sha256": release_summary["archive_sha256"],
                "sustained_internal_checksums_verified": True,
                "sustained_checksummed_files": release_summary["internal_checksummed_files"],
                "raw_quality_checksummed_files": release_summary[
                    "raw_quality_checksummed_files"
                ],
                "sustained_raw_confirmation_files": release_summary["raw_confirmation_files"],
                "sustained_raw_confirmation_samples": release_summary["raw_confirmation_samples"],
                "raw_quality_outputs": release_summary["raw_quality_outputs"],
                "sustained_matched_control_verified": release_summary["matched_control_verified"],
                "total_checksummed_files": (
                    checksum_result.checked + migration_verified.reproduction_checksums.checked
                    + release.checksums.checked
                    + performix["internal_checksums"]["checked"]
                    + deployment["checksummed_files"]
                ),
                "performix_archive_verified": True,
                "performix_archive_sha256": performix["archive_sha256"],
                "performix_internal_checksums_verified": True,
                "performix_checksummed_files": performix["internal_checksums"][
                    "checked"
                ],
                "comparison": "matched_control",
                "only_changed_control": release_summary["only_changed_control"],
            },
            "dataset": "BANKING77",
            "dataset_license": "CC-BY-4.0",
            "model": model_name,
            "model_id": model_id,
            "runtime": runtime_name,
            "optimization": "KleidiAI disabled -> enabled",
            "machine": runtime_lock["hardware"],
            "report_path": "../report/index.html",
            "release_url": release_url,
            "release_action": f"QasimKhan5x/ArmProof@{release_tag}",
            "contract_sha256": _sha256(
                root / "examples/armproof-reference" / reference_config["contract"]
            ),
        },
    }
    return payload
