"""ArmProof command-line entry point."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Sequence

from armproof.contracts import (
    ContractError,
    parse_contract,
    validate_comparison_identities,
)
from armproof.evidence import (
    EvidenceRecordError,
    comparison_to_dict,
    get_evidence_adapter,
    list_evidence_adapters,
    parse_comparison,
    verify_and_derive,
    verify_checksum_ledger,
)
from armproof.policy import decision_to_dict, evaluate_claims
from armproof.quality import evaluate_quality, load_quality_cases, quality_to_dict
from armproof.report import generate_report
from armproof.scaffold import create_scaffold
from armproof.workload import (
    SloPolicy,
    capacity_to_dict,
    find_sustainable_capacity,
    load_requests_jsonl,
    materialize_requests,
    run_closed_loop,
    run_open_loop,
    write_samples_jsonl,
)
from armproof.workload.load import send_http_json


def _json_object(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _evaluate(contract_path: Path, comparison_paths: Sequence[Path]) -> dict:
    contract = parse_contract(_json_object(contract_path))
    comparisons = [parse_comparison(_json_object(path)) for path in comparison_paths]
    validate_comparison_identities(contract, comparisons)
    return decision_to_dict(evaluate_claims(contract.claims, comparisons))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="armproof")
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser("verify", help="evaluate claims from normalized evidence")
    verify.add_argument("--contract", type=Path, required=True)
    verify.add_argument("--comparison", type=Path, action="append", required=True)
    verify.add_argument("--output", type=Path)
    capacity = subparsers.add_parser("capacity", help="run a fixed-SLO HTTP capacity search")
    capacity.add_argument("--endpoint", required=True)
    capacity.add_argument("--workload", type=Path, required=True)
    capacity.add_argument("--candidates-rps", required=True, help="ascending comma-separated values")
    capacity.add_argument("--measurement-seconds", type=float, required=True)
    capacity.add_argument("--p95-slo-ms", type=float, required=True)
    capacity.add_argument("--max-error-rate", type=float, default=0.01)
    capacity.add_argument("--workers", type=int, default=64)
    capacity.add_argument("--request-timeout", type=float, default=30.0)
    capacity.add_argument("--output", type=Path, required=True)
    quality = subparsers.add_parser("quality", help="run and score a BANKING77 quality set")
    quality.add_argument("--endpoint", required=True)
    quality.add_argument("--dataset", type=Path, required=True)
    quality.add_argument("--concurrency", type=int, default=4)
    quality.add_argument("--request-timeout", type=float, default=30.0)
    quality.add_argument("--output", type=Path, required=True)
    report = subparsers.add_parser("report", help="render an offline evidence report")
    report.add_argument("--decision", type=Path, required=True)
    report.add_argument("--summary", type=Path, required=True)
    report.add_argument("--comparison", type=Path)
    report.add_argument("--deployment-summary", type=Path)
    report.add_argument("--verification", type=Path)
    report.add_argument("--output", type=Path, required=True)
    evidence = subparsers.add_parser("evidence-verify", help="verify a relocated SHA-256 evidence ledger")
    evidence.add_argument("--checksums", type=Path, required=True)
    evidence.add_argument("--root", type=Path, required=True)
    evidence.add_argument("--source-prefix", default="/opt/armproof/evidence")
    subparsers.add_parser("adapters", help="list installed evidence adapters")
    init = subparsers.add_parser("init", help="scaffold a fail-closed HTTP adoption kit")
    init.add_argument("--endpoint", required=True)
    init.add_argument("--output", type=Path, required=True)
    ci = subparsers.add_parser("ci", help="evaluate and report from one ArmProof config")
    ci.add_argument("config", type=Path)
    ci.add_argument("--output", type=Path)
    ci.add_argument("--contract-sha256")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "capacity":
        return _run_capacity(args)
    if args.command == "quality":
        return _run_quality(args)
    if args.command == "report":
        try:
            index = generate_report(
                args.decision,
                args.summary,
                args.output,
                comparison_path=args.comparison,
                deployment_summary_path=args.deployment_summary,
                verification_path=args.verification,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"armproof: {exc}", file=sys.stderr)
            return 1
        print(index)
        return 0
    if args.command == "evidence-verify":
        try:
            result = verify_checksum_ledger(
                args.checksums, args.root, source_prefix=args.source_prefix
            )
        except (OSError, ValueError) as exc:
            print(f"armproof: {exc}", file=sys.stderr)
            return 1
        rendered = {
            "passed": result.passed,
            "checked": result.checked,
            "missing": list(result.missing),
            "mismatched": list(result.mismatched),
        }
        print(json.dumps(rendered, indent=2, sort_keys=True))
        return 0 if result.passed else 2
    if args.command == "adapters":
        print(json.dumps({"adapters": list(list_evidence_adapters())}, indent=2))
        return 0
    if args.command == "init":
        try:
            paths = create_scaffold(args.output.resolve(), args.endpoint)
        except (OSError, ValueError) as exc:
            print(f"armproof: {exc}", file=sys.stderr)
            return 1
        print(f"Created {len(paths)} files in {args.output.resolve()}")
        print("Next: open ADOPTION_CHECKLIST.md and replace the workload and identities.")
        return 0
    if args.command == "ci":
        return _run_ci(args)
    try:
        decision = _evaluate(args.contract, args.comparison)
    except (ValueError, ContractError, EvidenceRecordError) as exc:
        print(f"armproof: {exc}", file=sys.stderr)
        return 1
    rendered = json.dumps(decision, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if decision["passed"] else 2


def _run_ci(args: argparse.Namespace) -> int:
    try:
        config = _json_object(args.config)
        allowed = {
            "schema_version", "contract", "evidence", "deployment_summary", "output",
        }
        required = {"schema_version", "contract", "evidence"}
        if set(config) - allowed or not required <= set(config) or config["schema_version"] != "1.0.0":
            raise ValueError("config must be ArmProof 1.0 with no unknown fields")
        if not isinstance(config["contract"], str):
            raise ValueError("config contract must be a path")
        evidence_config = config["evidence"]
        if not isinstance(evidence_config, dict):
            raise ValueError("config evidence must be an object")
        adapter_id = evidence_config.get("adapter")
        if not isinstance(adapter_id, str) or not adapter_id:
            raise ValueError("config evidence must declare an adapter")
        base = args.config.resolve().parent
        contract_path = base / config["contract"]
        if args.contract_sha256 is not None:
            expected_contract_sha256 = args.contract_sha256
            if (
                len(expected_contract_sha256) != 64
                or any(char not in "0123456789abcdef" for char in expected_contract_sha256)
                or hashlib.sha256(contract_path.read_bytes()).hexdigest()
                != expected_contract_sha256
            ):
                raise ValueError("contract SHA-256 does not match the protected policy digest")
        contract = parse_contract(_json_object(contract_path))
        verified = get_evidence_adapter(adapter_id).verify(
            contract, evidence_config, base
        )
        deployment_value = config.get("deployment_summary")
        if deployment_value is not None and not isinstance(deployment_value, str):
            raise ValueError("config deployment_summary must be a path")
        deployment_path = base / deployment_value if deployment_value else None
        configured_output = config.get("output", "armproof-report")
        if not isinstance(configured_output, str) or not configured_output:
            raise ValueError("config output must be a non-empty path")
        output = args.output or (base / configured_output)
        decision = decision_to_dict(evaluate_claims(contract.claims, (verified.comparison,)))
        output.mkdir(parents=True, exist_ok=True)
        comparison_path = output / "comparison.json"
        comparison_path.write_text(
            json.dumps(comparison_to_dict(verified.comparison), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        summary_path = output / "summary.json"
        summary_path.write_text(
            json.dumps(dict(verified.summary), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        verification_path = output / "verification.json"
        verification_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "adapter": verified.adapter,
                    "comparison_source": "derived_from_raw_evidence",
                    "checksums": {
                        "passed": verified.checksums.passed,
                        "checked": verified.checksums.checked,
                        "missing": list(verified.checksums.missing),
                        "mismatched": list(verified.checksums.mismatched),
                    },
                    "reproduction_checksums": (
                        {
                            "passed": verified.reproduction_checksums.passed,
                            "checked": verified.reproduction_checksums.checked,
                            "missing": list(verified.reproduction_checksums.missing),
                            "mismatched": list(verified.reproduction_checksums.mismatched),
                        }
                        if verified.reproduction_checksums is not None else None
                    ),
                    "performix": dict(verified.performix) if verified.performix else None,
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        decision_path = output / "decision.json"
        decision_path.write_text(
            json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        generate_report(
            decision_path,
            summary_path,
            output,
            comparison_path=comparison_path,
            deployment_summary_path=deployment_path,
            verification_path=verification_path,
        )
    except (OSError, ValueError, ContractError, EvidenceRecordError) as exc:
        print(f"armproof: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0 if decision["passed"] else 2


def _run_capacity(args: argparse.Namespace) -> int:
    try:
        candidates = [float(item) for item in args.candidates_rps.split(",")]
        base = load_requests_jsonl(args.workload)
        if args.measurement_seconds <= 0:
            raise ValueError("measurement-seconds must be positive")
        samples_by_target = {}

        def run_candidate(target_rps: float):
            count = max(1, math.ceil(target_rps * args.measurement_seconds))
            requests = materialize_requests(base, count, f"rps-{target_rps:g}")
            samples = run_open_loop(
                requests,
                lambda item, scheduled: send_http_json(
                    args.endpoint, item, scheduled, args.request_timeout
                ),
                target_rps=target_rps,
                max_workers=args.workers,
            )
            samples_by_target[target_rps] = samples
            return samples

        result = find_sustainable_capacity(
            candidates,
            run_candidate,
            SloPolicy(args.p95_slo_ms, args.max_error_rate),
            args.measurement_seconds,
        )
    except (OSError, ValueError) as exc:
        print(f"armproof: {exc}", file=sys.stderr)
        return 1
    args.output.mkdir(parents=True, exist_ok=True)
    for target, samples in samples_by_target.items():
        write_samples_jsonl(args.output / f"requests-rps-{target:g}.jsonl", samples)
    rendered = json.dumps(capacity_to_dict(result), indent=2, sort_keys=True) + "\n"
    (args.output / "capacity.json").write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result.sustainable_rps > 0 else 2


def _run_quality(args: argparse.Namespace) -> int:
    try:
        cases = load_quality_cases(args.dataset)
        samples = run_closed_loop(
            [case.request for case in cases],
            lambda item, scheduled: send_http_json(
                args.endpoint, item, scheduled, args.request_timeout
            ),
            args.concurrency,
        )
        result = evaluate_quality(cases, samples)
    except (OSError, ValueError) as exc:
        print(f"armproof: {exc}", file=sys.stderr)
        return 1
    args.output.mkdir(parents=True, exist_ok=True)
    write_samples_jsonl(args.output / "quality-samples.jsonl", samples)
    rendered = json.dumps(quality_to_dict(result), indent=2, sort_keys=True) + "\n"
    (args.output / "quality.json").write_text(rendered, encoding="utf-8")
    summary = {
        "accuracy": result.accuracy,
        "macro_f1": result.macro_f1,
        "schema_valid_rate": result.schema_valid_rate,
        "total": result.total,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result.schema_valid_rate >= 0.99 and result.missing == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
