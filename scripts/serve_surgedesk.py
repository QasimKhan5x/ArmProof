#!/usr/bin/env python3
"""Serve SurgeDesk, matched live endpoints, and the local evidence verifier."""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from armproof.demo.live import build_prompt, compose_live_route  # noqa: E402
from armproof.demo.surgedesk import _queue_guard, build_surgedesk_payload  # noqa: E402
from armproof.contracts.parser import parse_contract  # noqa: E402
from armproof.cli import main as armproof_cli  # noqa: E402
from armproof.scaffold import create_scaffold  # noqa: E402
MAX_BODY_BYTES = 16 * 1024


@dataclass
class DeploymentState:
    """Session-local route state unlocked by the fresh release audit."""

    active_lane: str | None
    audit_experiment_id: str | None = None
    release_ready: bool = False
    promoted_at: str | None = None
    audited_deployment: dict[str, Any] | None = None
    _lock: Lock = field(default_factory=Lock, repr=False)

    def record_audit(self, receipt: dict[str, Any]) -> None:
        with self._lock:
            self.release_ready = receipt.get("passed") is True
            self.audit_experiment_id = (
                str(receipt["experiment_id"]) if self.release_ready else None
            )
            identity = receipt.get("deployment_identity")
            self.audited_deployment = (
                dict(identity)
                if self.release_ready and isinstance(identity, dict)
                else None
            )

    def promote(self, live_identity: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if (
                not self.release_ready
                or not self.audit_experiment_id
                or not self.audited_deployment
            ):
                raise ValueError("optimized lane requires a fresh passing audit")
            expected = self.audited_deployment
            compared = {
                "model_identity": live_identity.get("model_identity"),
                "source_artifact_sha256": live_identity.get("source_artifact_sha256"),
                "runtime_lock_sha256": live_identity.get("runtime_lock_sha256"),
                "runtime_artifact_ledger_sha256": live_identity.get(
                    "runtime_artifact_ledger_sha256"
                ),
                "runtime": live_identity.get("runtime"),
                "runtime_version": live_identity.get("runtime_version"),
                "architecture": live_identity.get("architecture"),
                "threads": live_identity.get("threads_per_lane"),
                "cpu_affinity": live_identity.get("cpu_affinity"),
                "instance_type": live_identity.get("instance_type"),
                "instance_identity_source": live_identity.get(
                    "instance_identity_source"
                ),
                "controls": {
                    "baseline": {
                        "mlas.disable_kleidiai": live_identity.get("baseline_control")
                    },
                    "optimized": {
                        "mlas.disable_kleidiai": live_identity.get("optimized_control")
                    },
                },
            }
            required = {
                key: expected[key]
                for key in (
                    "model_identity", "source_artifact_sha256",
                    "runtime_lock_sha256", "runtime_artifact_ledger_sha256",
                    "runtime", "runtime_version",
                    "architecture", "threads", "cpu_affinity",
                    "instance_type", "instance_identity_source", "controls",
                )
            }
            if compared != required:
                raise ValueError("live deployment identity differs from audited release")
            self.active_lane = "optimized"
            self.promoted_at = datetime.now(UTC).isoformat(timespec="milliseconds")
            return self._snapshot_unlocked()

    def authorize_active_route(
        self,
        lane: str,
        observed_identity: dict[str, Any],
    ) -> str | None:
        """Bind every optimized response to the release that authorized it."""
        with self._lock:
            if lane != self.active_lane:
                raise ValueError("route lane differs from the active deployment")
            if lane == "baseline":
                return None
            if (
                lane != "optimized"
                or not self.release_ready
                or not self.audit_experiment_id
                or not self.audited_deployment
            ):
                raise ValueError("optimized route lacks an active release authorization")
            expected = self.audited_deployment
            compared = {
                key: observed_identity.get(key)
                for key in (
                    "model_identity", "source_artifact_sha256",
                    "runtime_lock_sha256", "runtime_artifact_ledger_sha256",
                    "runtime", "runtime_version",
                    "architecture", "threads", "cpu_affinity", "instance_type",
                    "instance_identity_source",
                )
            }
            required = {key: expected[key] for key in compared}
            expected_control = expected["controls"]["optimized"]
            if (
                compared != required
                or observed_identity.get("optimization_control") != expected_control
            ):
                self._revoke_optimized_route_unlocked()
                raise ValueError("optimized route drifted from audited release")
            return self.audit_experiment_id

    def revoke_optimized_route(self) -> None:
        """Return to the standard lane when the active candidate cannot be trusted."""
        with self._lock:
            self._revoke_optimized_route_unlocked()

    def _revoke_optimized_route_unlocked(self) -> None:
        if self.active_lane != "optimized":
            return
        self.active_lane = "baseline"
        self.audit_experiment_id = None
        self.release_ready = False
        self.promoted_at = None
        self.audited_deployment = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._snapshot_unlocked()

    def _snapshot_unlocked(self) -> dict[str, Any]:
        return {
            "active_lane": self.active_lane,
            "audit_experiment_id": self.audit_experiment_id,
            "release_ready": self.release_ready,
            "promoted_at": self.promoted_at,
        }


def _core_set(value: str) -> frozenset[int]:
    cores: set[int] = set()
    for part in value.split(","):
        bounds = part.strip().split("-", 1)
        if not bounds[0].isdigit() or (len(bounds) == 2 and not bounds[1].isdigit()):
            raise ValueError(f"invalid CPU core group: {value}")
        start = int(bounds[0])
        end = int(bounds[-1])
        if start > end:
            raise ValueError(f"invalid CPU core group: {value}")
        cores.update(range(start, end + 1))
    if not cores:
        raise ValueError("CPU core group cannot be empty")
    return frozenset(cores)


def _health_url(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    return parsed._replace(path="/health", query="", fragment="").geturl()


def _probe_lane(config: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    endpoint = config["endpoint"]
    if not endpoint:
        return False, "endpoint missing", {}
    try:
        with urllib.request.urlopen(_health_url(str(endpoint)), timeout=2) as response:
            payload = json.load(response)
        if not isinstance(payload, dict):
            return False, "health response is not an object", {}
        expected_cores = sorted(config["expected_cores"])
        observed_control = payload.get("optimization_control", {}).get(
            "mlas.disable_kleidiai"
        )
        if (
            payload.get("ready") is not True
            or payload.get("backend") != config["expected_backend"]
            or payload.get("cpu_affinity") != expected_cores
            or observed_control != config["expected_control"]
            or payload.get("runtime") != "onnxruntime-genai"
            or payload.get("architecture") not in {"aarch64", "arm64"}
            or not isinstance(payload.get("runtime_version"), str)
            or not isinstance(payload.get("model_identity"), str)
            or len(payload["model_identity"]) != 64
            or any(character not in "0123456789abcdef" for character in payload["model_identity"])
            or not isinstance(payload.get("source_artifact_sha256"), str)
            or len(payload["source_artifact_sha256"]) != 64
            or any(
                character not in "0123456789abcdef"
                for character in payload["source_artifact_sha256"]
            )
            or payload.get("threads") != len(expected_cores)
            or not isinstance(payload.get("runtime_lock_sha256"), str)
            or len(payload["runtime_lock_sha256"]) != 64
            or any(
                character not in "0123456789abcdef"
                for character in payload["runtime_lock_sha256"]
            )
            or not isinstance(payload.get("runtime_artifact_ledger_sha256"), str)
            or len(payload["runtime_artifact_ledger_sha256"]) != 64
            or any(
                character not in "0123456789abcdef"
                for character in payload["runtime_artifact_ledger_sha256"]
            )
            or not isinstance(payload.get("instance_type"), str)
            or not payload["instance_type"]
            or payload.get("instance_identity_source") != "aws-imdsv2"
        ):
            return False, "health identity, control, or CPU affinity mismatch", payload
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError):
        return False, "health check failed", {}
    return True, "verified from runtime configuration", payload


def _match_lane_identity(
    baseline: tuple[bool, str, dict[str, Any]],
    optimized: tuple[bool, str, dict[str, Any]],
) -> tuple[bool, str, dict[str, Any]]:
    if not baseline[0] or not optimized[0]:
        return False, "one or both lane probes failed", {}
    left = baseline[2]
    right = optimized[2]
    matched_fields = (
        "model_identity", "source_artifact_sha256", "runtime_lock_sha256",
        "runtime_artifact_ledger_sha256",
        "runtime", "runtime_version", "threads", "architecture",
        "cpu_affinity", "instance_type", "instance_identity_source",
    )
    if any(left.get(field) != right.get(field) for field in matched_fields):
        return False, "model, runtime, or thread identity mismatch", {}
    return True, "matched", {
        "model_identity": left["model_identity"],
        "source_artifact_sha256": left["source_artifact_sha256"],
        "runtime_lock_sha256": left["runtime_lock_sha256"],
        "runtime_artifact_ledger_sha256": left["runtime_artifact_ledger_sha256"],
        "runtime": left["runtime"],
        "runtime_version": left["runtime_version"],
        "threads_per_lane": left["threads"],
        "architecture": left["architecture"],
        "cpu_affinity": left["cpu_affinity"],
        "instance_type": left["instance_type"],
        "instance_identity_source": left["instance_identity_source"],
        "changed_control": "mlas.disable_kleidiai",
        "baseline_control": left["optimization_control"]["mlas.disable_kleidiai"],
        "optimized_control": right["optimization_control"]["mlas.disable_kleidiai"],
    }


def _response_identity_matches(
    upstream: dict[str, Any], expected_health: dict[str, Any]
) -> bool:
    response_identity = upstream.get("runtime_identity")
    identity_fields = (
        "model_identity", "source_artifact_sha256", "runtime_lock_sha256",
        "runtime_artifact_ledger_sha256", "instance_type",
        "instance_identity_source", "runtime", "runtime_version", "threads",
        "architecture", "cpu_affinity", "optimization_control",
    )
    return isinstance(response_identity, dict) and all(
        response_identity.get(field) == expected_health.get(field)
        for field in identity_fields
    )


def _audit_receipt(payload: dict[str, Any], elapsed_ms: float) -> dict[str, Any]:
    decision = payload["proof"]
    evidence = payload["provenance"]["evidence"]
    mixed = payload["capacity"]["mixes"]["mixed"]
    return {
        "passed": decision["decision"] == "PASS",
        "experiment_id": payload["provenance"]["experiment_id"],
        "adapter": decision["adapter_id"],
        "claims_verified": decision["verified_claims"],
        "claims": decision["claims"],
        "raw_request_outcomes": evidence["sustained_raw_confirmation_samples"],
        "raw_quality_outputs": evidence["raw_quality_outputs"],
        "confirmation_files": evidence["sustained_raw_confirmation_files"],
        "archive_sha256": evidence["sustained_archive_sha256"],
        "matched_control": evidence["sustained_matched_control_verified"],
        "deployment_identity": decision["live_deployment_identity"],
        "capacity": {
            "trial_matrix": mixed["trial_matrix"],
            "optimized_pass_rps": mixed["optimized_sustainable_rps"],
            "baseline_fail_rps": mixed["baseline_fail_rps"],
            "minimum_ratio": mixed["minimum_capacity_ratio"],
            "confirmations": mixed["confirmations_per_treatment"],
            "confirmation_seconds": mixed["confirmation_seconds"],
            "slo_ms": payload["capacity"]["slo_ms"],
            "rate_selection": payload["capacity"]["rate_selection"],
        },
        "arm": {
            "performix_disabled_sample_share_percent": decision["performix"][
                "disabled_kai_sample_share_percent"
            ],
            "performix_enabled_sample_share_percent": decision["performix"][
                "enabled_kai_sample_share_percent"
            ],
            "linux_perf_cycle_share_percent": decision[
                "kleidiai_cycle_callchain_share_percent"
            ],
            "kernel": decision["performix"]["kernel_family"],
            "engine_version": decision["performix"]["engine_version"],
            "cpu": decision["performix"]["cpu"],
            "enabled_function_samples": decision["performix"][
                "enabled_function_samples"
            ],
            "disabled_function_samples": decision["performix"][
                "disabled_function_samples"
            ],
            "disabled_kai_function_samples": decision["performix"][
                "disabled_kai_function_samples"
            ],
            "enabled_kai_function_samples": decision["performix"][
                "enabled_kai_function_samples"
            ],
            "scope_note": decision["performix"]["scope_note"],
            "pmu_capability_note": decision["performix"]["pmu_capability_note"],
        },
        "supporting": {
            "direct_speedup_min": decision["direct_speedup_min"],
            "direct_speedup_max": decision["direct_speedup_max"],
            "direct_shape_gains": decision["direct_shape_gains"],
            "artifact_reduction_percent": decision["artifact_reduction_percent"],
            "peak_pss_reduction_percent": decision["peak_pss_reduction_percent"],
            "migration_quality_delta_pp": decision["migration_quality_delta_pp"],
            "migration_int4_quality_correct": decision[
                "migration_int4_quality_correct"
            ],
            "migration_bf16_quality_correct": decision[
                "migration_bf16_quality_correct"
            ],
            "migration_quality_total": decision["migration_quality_total"],
        },
        "elapsed_ms": elapsed_ms,
    }


def _adoption_receipt() -> dict[str, Any]:
    """Generate a starter and prove that its empty evidence state fails closed."""
    with tempfile.TemporaryDirectory(prefix="armproof-adoption-") as directory:
        output = Path(directory) / "my-arm-service"
        create_scaffold(output, "http://127.0.0.1:8000/infer")
        contract_path = output / "contract.json"
        contract = parse_contract(json.loads(contract_path.read_text(encoding="utf-8")))
        contract_sha256 = hashlib.sha256(contract_path.read_bytes()).hexdigest()
        workflow = (output / ".github/workflows/armproof.yml").read_text(
            encoding="utf-8"
        )
        if f"contract-sha256: {contract_sha256}" not in workflow:
            raise ValueError("generated workflow is not bound to its contract")
        config = json.loads((output / "armproof.json").read_text(encoding="utf-8"))
        if config.get("contract") != "contract.json":
            raise ValueError("generated config is not bound to its contract")
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            initial_ci_exit_code = armproof_cli([
                "ci",
                str(output / "armproof.json"),
                "--contract-sha256",
                contract_sha256,
            ])
        if initial_ci_exit_code == 0:
            raise ValueError("empty adoption starter unexpectedly passed ArmProof CI")
        initial_ci_output = f"{stderr.getvalue()}\n{stdout.getvalue()}"
        if "No measured evidence found" not in initial_ci_output:
            raise ValueError("empty adoption starter failed for an unexpected reason")
        archive_buffer = io.BytesIO()
        generated_files = sorted(
            candidate for candidate in output.rglob("*") if candidate.is_file()
        )
        with zipfile.ZipFile(
            archive_buffer, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for path in generated_files:
                name = str(Path("my-arm-service") / path.relative_to(output))
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())
        return {
            "generated_files": [
                str(path.relative_to(output)) for path in generated_files
            ],
            "validation_status": "BLOCKED",
            "validation_detail": (
                f"Fresh ArmProof CI exited {initial_ci_exit_code} because measured "
                "evidence is absent; the Action is bound to this contract digest"
            ),
            "initial_ci_exit_code": initial_ci_exit_code,
            "initial_ci_reason": "no measured evidence found",
            "workflow": workflow,
            "contract_sha256": contract_sha256,
            "archive_name": "armproof-service-starter.zip",
            "archive_base64": base64.b64encode(archive_buffer.getvalue()).decode("ascii"),
        }


def _upstream_request(
    endpoint: str,
    *,
    text: str,
    categories: list[str],
    request_id: str,
    expected_backend: str | None,
) -> tuple[dict[str, Any], float, str]:
    body = json.dumps(
        {
            "request_id": request_id,
            "prompt": build_prompt(text, categories),
            "max_new_tokens": 32,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started_at = datetime.now(UTC).isoformat(timespec="milliseconds")
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=60) as response:
        upstream = json.load(response)
    elapsed_ms = (time.perf_counter() - started) * 1000
    if not isinstance(upstream, dict):
        raise ValueError("upstream response must be a JSON object")
    if expected_backend and upstream.get("backend") != expected_backend:
        raise ValueError(
            f"backend identity mismatch: expected {expected_backend}, "
            f"observed {upstream.get('backend', 'missing')}"
        )
    if upstream.get("request_id") != request_id:
        raise ValueError(
            f"request identity mismatch: expected {request_id}, "
            f"observed {upstream.get('request_id', 'missing')}"
        )
    return upstream, elapsed_ms, started_at


def handler_for(
    *,
    baseline_endpoint: str | None = None,
    optimized_endpoint: str | None = None,
    baseline_cores: str = "0-15",
    optimized_cores: str = "0-15",
) -> type[SimpleHTTPRequestHandler]:
    if baseline_endpoint and optimized_endpoint and baseline_endpoint == optimized_endpoint:
        raise ValueError("matched endpoints must be distinct")
    baseline_core_set = _core_set(baseline_cores)
    optimized_core_set = _core_set(optimized_cores)
    if len(baseline_core_set) != len(optimized_core_set):
        raise ValueError("matched endpoint core groups must have equal size")
    if baseline_core_set & optimized_core_set and baseline_core_set != optimized_core_set:
        raise ValueError("matched endpoint core groups must be identical or disjoint")
    guard, _, _ = _queue_guard(ROOT)
    categories = json.loads(
        (ROOT / "data/banking77/source/categories.json").read_text(encoding="utf-8")
    )
    lanes = {
        "baseline": {
            "endpoint": baseline_endpoint,
            "expected_backend": "kleidiai-disabled",
            "core_group": baseline_cores,
            "expected_cores": baseline_core_set,
            "expected_control": "1",
            "label": "KleidiAI disabled",
        },
        "optimized": {
            "endpoint": optimized_endpoint,
            "expected_backend": "kleidiai-enabled",
            "core_group": optimized_cores,
            "expected_cores": optimized_core_set,
            "expected_control": "0",
            "label": "KleidiAI enabled",
        },
    }
    deployment = DeploymentState(
        active_lane=(
            "baseline" if baseline_endpoint and optimized_endpoint else None
        )
    )

    def active_route() -> tuple[str | None, dict[str, Any] | None]:
        lane = deployment.snapshot()["active_lane"]
        if lane in lanes:
            return lane, lanes[str(lane)]
        return None, None

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(ROOT / "surgedesk"), **kwargs)

        def end_headers(self) -> None:
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
                "frame-ancestors 'none'; base-uri 'none'",
            )
            super().end_headers()

        def translate_path(self, path: str) -> str:
            requested = unquote(urlsplit(path).path)
            relative = requested.removeprefix("/surgedesk/")
            if requested in {"/surgedesk", "/surgedesk/"}:
                relative = "index.html"
            target = (ROOT / "surgedesk" / relative).resolve()
            public_root = (ROOT / "surgedesk").resolve()
            if not target.is_relative_to(public_root):
                return str(public_root / "__not_found__")
            return str(target)

        def _json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _audit_stream(self) -> None:
            self.send_response(HTTPStatus.OK.value)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True

            def emit(event_type: str, payload: dict[str, Any]) -> None:
                line = json.dumps(
                    {"type": event_type, **payload}, separators=(",", ":")
                ).encode("utf-8") + b"\n"
                self.wfile.write(line)
                self.wfile.flush()

            started = time.perf_counter()
            try:
                payload = build_surgedesk_payload(
                    ROOT,
                    on_audit_stage=lambda stage, detail: emit(
                        "stage",
                        {
                            "stage": stage,
                            "detail": detail,
                            "elapsed_ms": (time.perf_counter() - started) * 1000,
                        },
                    ),
                )
                receipt = _audit_receipt(
                    payload, (time.perf_counter() - started) * 1000
                )
                deployment.record_audit(receipt)
                emit("result", {"receipt": receipt})
            except Exception as exc:
                emit("error", {"error": str(exc)})

        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY_BYTES:
                raise ValueError("invalid request size")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("request body must be a JSON object")
            return payload

        @staticmethod
        def _text(payload: dict[str, Any]) -> str:
            text = payload.get("text")
            if not isinstance(text, str) or not 1 <= len(text.strip()) <= 4000:
                raise ValueError("text must contain 1 to 4000 characters")
            return text.strip()

        def do_GET(self) -> None:
            if self.path == "/surgedesk/live-status.json":
                lane_status = {
                    name: _probe_lane(row) for name, row in lanes.items()
                }
                matched_available, matched_reason, matched_identity = _match_lane_identity(
                    lane_status["baseline"], lane_status["optimized"]
                )
                _, route_config = active_route()
                route_available = bool(route_config and _probe_lane(route_config)[0])
                self._json(
                    HTTPStatus.OK,
                    {
                        "live_available": route_available,
                        "matched_lanes_available": matched_available,
                        "matched_identity": matched_identity,
                        "matched_status": matched_reason,
                        "audit_available": True,
                        "mode": "live" if route_config else "recorded",
                        "deployment": deployment.snapshot(),
                        "lanes": {
                            name: {
                                "backend": row["expected_backend"],
                                "core_group": row["core_group"],
                                "verified": lane_status[name][0],
                                "status": lane_status[name][1],
                                "observed_control": lane_status[name][2]
                                .get("optimization_control", {})
                                .get("mlas.disable_kleidiai"),
                            }
                            for name, row in lanes.items()
                        },
                    },
                )
                return
            if self.path == "/":
                self.send_response(HTTPStatus.FOUND.value)
                self.send_header("Location", "/surgedesk/")
                self.end_headers()
                return
            if self.path != "/surgedesk" and not self.path.startswith("/surgedesk/"):
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            super().do_GET()

        def do_POST(self) -> None:
            try:
                if self.path == "/api/audit-stream":
                    self._audit_stream()
                    return
                if self.path == "/api/audit":
                    started = time.perf_counter()
                    payload = build_surgedesk_payload(ROOT)
                    receipt = _audit_receipt(
                        payload, (time.perf_counter() - started) * 1000
                    )
                    deployment.record_audit(receipt)
                    self._json(
                        HTTPStatus.OK,
                        receipt,
                    )
                    return
                if self.path == "/api/adoption":
                    self._json(HTTPStatus.OK, _adoption_receipt())
                    return
                if self.path == "/api/promote":
                    lane_probes = {
                        name: _probe_lane(config) for name, config in lanes.items()
                    }
                    matched, reason, live_identity = _match_lane_identity(
                        lane_probes["baseline"], lane_probes["optimized"]
                    )
                    if not matched:
                        self._json(
                            HTTPStatus.CONFLICT,
                            {"error": "matched_runtime_identity_changed", "detail": reason},
                        )
                        return
                    promoted = deployment.promote(live_identity)
                    self._json(
                        HTTPStatus.OK,
                        {
                            **promoted,
                            "backend": lanes["optimized"]["expected_backend"],
                            "core_group": lanes["optimized"]["core_group"],
                            "runtime_identity": live_identity,
                        },
                    )
                    return
                if self.path == "/api/shadow-compare":
                    if deployment.snapshot()["active_lane"] != "baseline":
                        self._json(
                            HTTPStatus.CONFLICT,
                            {"error": "shadow comparison is only available before promotion"},
                        )
                        return
                    lane_probes = {
                        name: _probe_lane(config) for name, config in lanes.items()
                    }
                    matched, reason, _ = _match_lane_identity(
                        lane_probes["baseline"], lane_probes["optimized"]
                    )
                    if not matched:
                        self._json(
                            HTTPStatus.CONFLICT,
                            {"error": "matched_runtime_identity_changed", "detail": reason},
                        )
                        return
                    payload = self._body()
                    text = self._text(payload)
                    results: dict[str, Any] = {}
                    for lane_name in ("baseline", "optimized"):
                        config = lanes[lane_name]
                        upstream, elapsed_ms, _ = _upstream_request(
                            str(config["endpoint"]),
                            text=text,
                            categories=categories,
                            request_id=f"shadow-{lane_name}-{uuid.uuid4().hex[:10]}",
                            expected_backend=str(config["expected_backend"]),
                        )
                        if not _response_identity_matches(
                            upstream, lane_probes[lane_name][2]
                        ):
                            self._json(
                                HTTPStatus.CONFLICT,
                                {"error": f"{lane_name}_inference_identity_mismatch"},
                            )
                            return
                        result = compose_live_route(text, upstream, guard, categories)
                        result.update({
                            "gateway_latency_ms": elapsed_ms,
                            "deployment_lane": lane_name,
                            "observed_at": datetime.now(UTC).isoformat(),
                            "runtime_identity": upstream["runtime_identity"],
                            "release_audit_id": None,
                            "shadow_only": lane_name == "optimized",
                        })
                        results[lane_name] = result
                    baseline_ms = results["baseline"]["gateway_latency_ms"]
                    optimized_ms = results["optimized"]["gateway_latency_ms"]
                    self._json(
                        HTTPStatus.OK,
                        {
                            "comparison_id": f"compare-{uuid.uuid4().hex[:12]}",
                            "execution": "sequential_shadow",
                            "serving_lane": "baseline",
                            "capacity_evidence": False,
                            "same_queue": (
                                results["baseline"]["queue"]
                                == results["optimized"]["queue"]
                            ),
                            "observed_latency_ratio": (
                                baseline_ms / optimized_ms if optimized_ms > 0 else None
                            ),
                            "lanes": results,
                        },
                    )
                    return
                if self.path == "/api/route":
                    active_lane, route_config = active_route()
                    if not route_config:
                        self._json(
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            {"error": "live_endpoint_not_configured"},
                        )
                        return
                    route_probe = _probe_lane(route_config)
                    if not route_probe[0]:
                        deployment.revoke_optimized_route()
                        self._json(
                            HTTPStatus.CONFLICT,
                            {"error": "route_runtime_identity_changed"},
                        )
                        return
                    payload = self._body()
                    text = self._text(payload)
                    upstream, elapsed_ms, _ = _upstream_request(
                        str(route_config["endpoint"]),
                        text=text,
                        categories=categories,
                        request_id=f"surgedesk-{uuid.uuid4().hex[:12]}",
                        expected_backend=str(route_config["expected_backend"]),
                    )
                    if not _response_identity_matches(upstream, route_probe[2]):
                        deployment.revoke_optimized_route()
                        self._json(
                            HTTPStatus.CONFLICT,
                            {"error": "route_inference_identity_mismatch"},
                        )
                        return
                    try:
                        release_audit_id = deployment.authorize_active_route(
                            str(active_lane), upstream["runtime_identity"]
                        )
                    except ValueError as exc:
                        self._json(
                            HTTPStatus.CONFLICT,
                            {"error": "active_release_identity_drift", "detail": str(exc)},
                        )
                        return
                    result = compose_live_route(text, upstream, guard, categories)
                    result["gateway_latency_ms"] = elapsed_ms
                    result["deployment_lane"] = active_lane
                    result["observed_at"] = datetime.now(UTC).isoformat()
                    result["runtime_identity"] = upstream["runtime_identity"]
                    result["release_audit_id"] = release_audit_id
                    self._json(HTTPStatus.OK, result)
                    return
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            except KeyError as exc:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": f"evidence schema is incomplete: {exc.args[0]}"},
                )
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except (urllib.error.URLError, TimeoutError) as exc:
                self._json(HTTPStatus.BAD_GATEWAY, {"error": type(exc).__name__})

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--baseline-endpoint", default=os.environ.get("SURGEDESK_BASELINE_ENDPOINT")
    )
    parser.add_argument(
        "--optimized-endpoint", default=os.environ.get("SURGEDESK_OPTIMIZED_ENDPOINT")
    )
    parser.add_argument("--baseline-cores", default="0-15")
    parser.add_argument("--optimized-cores", default="0-15")
    args = parser.parse_args()
    print(f"SurgeDesk: http://{args.host}:{args.port}/surgedesk/")
    print(
        "Live route: "
        f"{'configured; enabled after matched identity probes' if args.baseline_endpoint and args.optimized_endpoint else 'disabled'}"
    )
    ThreadingHTTPServer(
        (args.host, args.port),
        handler_for(
            baseline_endpoint=args.baseline_endpoint,
            optimized_endpoint=args.optimized_endpoint,
            baseline_cores=args.baseline_cores,
            optimized_cores=args.optimized_cores,
        ),
    ).serve_forever()


if __name__ == "__main__":
    main()
