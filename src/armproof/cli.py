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
from armproof.evidence.supporting import verified_deployment_summary
from armproof.evidence.publication import verify_preregistration_publication
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


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


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
    seal = subparsers.add_parser(
        "seal", help="write a deterministic SHA-256 ledger for collected evidence"
    )
    seal.add_argument("config", type=Path)
    seal.add_argument("--source-prefix", default="/opt/armproof/evidence")
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
    if args.command == "seal":
        return _run_seal(args)
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


def _run_seal(args: argparse.Namespace) -> int:
    """Hash collected evidence without implying that the evidence passes policy."""
    try:
        config = _json_object(args.config)
        evidence = config.get("evidence")
        if not isinstance(evidence, dict):
            raise ValueError("config evidence must be an object")
        root_value = evidence.get("root")
        ledger_value = evidence.get("checksums")
        if not isinstance(root_value, str) or not isinstance(ledger_value, str):
            raise ValueError("seal requires evidence root and checksums paths")
        base = args.config.resolve().parent
        root = (base / root_value).resolve()
        ledger = (base / ledger_value).resolve()
        if not root.is_dir():
            raise ValueError(f"evidence root does not exist: {root}")
        if not ledger.is_relative_to(root):
            raise ValueError("checksum ledger must be inside the evidence root")
        prefix = args.source_prefix.rstrip("/")
        if not prefix.startswith("/") or not prefix:
            raise ValueError("source prefix must be an absolute POSIX path")
        rows: list[str] = []
        for path in sorted(root.rglob("*")):
            if path == ledger or path.is_dir():
                continue
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"evidence contains an unsupported path: {path}")
            relative = path.relative_to(root).as_posix()
            rows.append(f"{_file_sha256(path)}  {prefix}/{relative}")
        if not rows:
            raise ValueError("evidence root contains no files to seal")
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text("\n".join(rows) + "\n", encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"armproof: {exc}", file=sys.stderr)
        return 1
    print(f"Sealed {len(rows)} evidence files in {ledger}")
    print(f"Next: armproof ci {args.config}")
    return 0


def _run_ci(args: argparse.Namespace) -> int:
    try:
        config = _json_object(args.config)
        allowed = {
            "schema_version", "contract", "evidence", "deployment_summary",
            "supporting_evidence", "publication_proof", "output",
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
        publication_value = config.get("publication_proof")
        publication = None
        if publication_value is not None:
            if (
                not isinstance(publication_value, dict)
                or set(publication_value) != {"record", "project_bundle"}
                or not all(
                    isinstance(publication_value[field], str)
                    and publication_value[field]
                    for field in ("record", "project_bundle")
                )
                or not all(
                    isinstance(evidence_config.get(field), str)
                    for field in ("preregistration", "archive", "archive_sha256")
                )
            ):
                raise ValueError("config publication_proof is invalid")
            publication = verify_preregistration_publication(
                base / publication_value["record"],
                preregistration_path=base / evidence_config["preregistration"],
                project_bundle_path=base / publication_value["project_bundle"],
                evidence_archive_path=base / evidence_config["archive"],
                expected_evidence_archive_sha256=evidence_config["archive_sha256"],
                repository_path=_git_root(base),
            )
        deployment_value = config.get("deployment_summary")
        if deployment_value is not None and not isinstance(deployment_value, str):
            raise ValueError("config deployment_summary must be a path")
        supporting_value = config.get("supporting_evidence")
        if deployment_value is not None and supporting_value is None:
            raise ValueError(
                "config deployment_summary requires hash-locked supporting_evidence"
            )
        if supporting_value is not None and (
            not isinstance(supporting_value, dict)
            or set(supporting_value) != {"root", "lock"}
            or not all(
                isinstance(supporting_value[field], str) and supporting_value[field]
                for field in ("root", "lock")
            )
        ):
            raise ValueError("config supporting_evidence requires root and lock paths")
        deployment = None
        supporting = None
        source_deployment_path = base / deployment_value if deployment_value else None
        if source_deployment_path is not None and supporting_value is not None:
            deployment, supporting = verified_deployment_summary(
                source_deployment_path,
                evidence_root=base / supporting_value["root"],
                lock_path=base / supporting_value["lock"],
            )
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
        decision_path = output / "decision.json"
        decision_path.write_text(
            json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        verification_path = output / "verification.json"
        verification_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "adapter": verified.adapter,
                    "comparison_source": "derived_from_raw_evidence",
                    "artifact_bindings": {
                        "contract_sha256": _file_sha256(contract_path),
                        "comparison_sha256": _file_sha256(comparison_path),
                        "summary_sha256": _file_sha256(summary_path),
                        "decision_sha256": _file_sha256(decision_path),
                    },
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
                    "supporting_evidence": (
                        {
                            "experiment_id": supporting["experiment_id"],
                            "checksummed_files": supporting["checksummed_files"],
                            "derivation": (
                                "locked_aggregate_footprint_and_raw_timing_repetitions"
                            ),
                        }
                        if supporting is not None else None
                    ),
                    "preregistration_publication": publication,
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        deployment_path = None
        if deployment is not None:
            deployment_path = output / "deployment-summary.json"
            deployment_path.write_text(
                json.dumps(deployment, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
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
