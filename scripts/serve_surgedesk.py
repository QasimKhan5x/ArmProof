#!/usr/bin/env python3
"""Serve SurgeDesk, matched live endpoints, and the local evidence verifier."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from armproof.demo.live import build_prompt, compose_live_route  # noqa: E402
from armproof.demo.surgedesk import _queue_guard, build_surgedesk_payload  # noqa: E402
from armproof.contracts import parse_contract  # noqa: E402
from armproof.evidence.sustained_audit import derive_sustained_audit  # noqa: E402
from armproof.scaffold import create_scaffold  # noqa: E402


MAX_BODY_BYTES = 16 * 1024


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
            or payload.get("threads") != len(expected_cores)
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
        "model_identity", "runtime", "runtime_version", "threads", "architecture"
    )
    if any(left.get(field) != right.get(field) for field in matched_fields):
        return False, "model, runtime, or thread identity mismatch", {}
    return True, "matched", {
        "model_identity": left["model_identity"],
        "runtime": left["runtime"],
        "runtime_version": left["runtime_version"],
        "threads_per_lane": left["threads"],
        "architecture": left["architecture"],
        "changed_control": "mlas.disable_kleidiai",
        "baseline_control": left["optimization_control"]["mlas.disable_kleidiai"],
        "optimized_control": right["optimization_control"]["mlas.disable_kleidiai"],
    }


def _response_identity_matches(
    upstream: dict[str, Any], expected_health: dict[str, Any]
) -> bool:
    response_identity = upstream.get("runtime_identity")
    identity_fields = (
        "model_identity", "runtime", "runtime_version", "threads",
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
        "raw_request_outcomes": evidence["sustained_raw_confirmation_samples"],
        "confirmation_files": evidence["sustained_raw_confirmation_files"],
        "archive_sha256": evidence["sustained_archive_sha256"],
        "matched_control": evidence["sustained_matched_control_verified"],
        "capacity": {
            "trial_matrix": mixed["trial_matrix"],
            "optimized_pass_rps": mixed["optimized_sustainable_rps"],
            "baseline_fail_rps": mixed["baseline_fail_rps"],
            "minimum_ratio": mixed["minimum_capacity_ratio"],
            "confirmations": mixed["confirmations_per_treatment"],
            "confirmation_seconds": mixed["confirmation_seconds"],
        },
        "original_gate": {
            "passed": payload["provenance"]["original_gate_passed"],
            "required_probe_failures": mixed["confirmations_per_treatment"],
            "observed_probe_failures": mixed["optimized_probe_failures"],
            "observed_probe_passes": mixed["optimized_probe_passes"],
            "probe_rps": mixed["optimized_probe_rps"],
            "exact_lower_ratio": mixed["minimum_capacity_ratio"],
            "exact_upper_ratio": (
                mixed["optimized_probe_rps"] / mixed["baseline_sustainable_rps"]
            ),
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
        },
        "elapsed_ms": elapsed_ms,
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
    endpoint: str | None = None,
    *,
    baseline_endpoint: str | None = None,
    optimized_endpoint: str | None = None,
    baseline_cores: str = "0-7",
    optimized_cores: str = "8-15",
) -> type[SimpleHTTPRequestHandler]:
    if baseline_endpoint and optimized_endpoint and baseline_endpoint == optimized_endpoint:
        raise ValueError("matched endpoints must be distinct")
    baseline_core_set = _core_set(baseline_cores)
    optimized_core_set = _core_set(optimized_cores)
    if len(baseline_core_set) != len(optimized_core_set):
        raise ValueError("matched endpoint core groups must have equal size")
    if baseline_core_set & optimized_core_set:
        raise ValueError("matched endpoint core groups must be disjoint")
    guard, _, _ = _queue_guard(ROOT)
    categories = json.loads(
        (ROOT / "data/banking77/source/categories.json").read_text(encoding="utf-8")
    )
    route_endpoint = endpoint or optimized_endpoint
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
                if route_endpoint == optimized_endpoint:
                    route_available = lane_status["optimized"][0]
                elif route_endpoint:
                    route_config = {
                        **lanes["optimized"],
                        "endpoint": route_endpoint,
                    }
                    route_available = _probe_lane(route_config)[0]
                else:
                    route_available = False
                self._json(
                    HTTPStatus.OK,
                    {
                        "live_available": route_available,
                        "matched_surge_available": matched_available,
                        "matched_identity": matched_identity,
                        "matched_status": matched_reason,
                        "audit_available": True,
                        "mode": "live" if route_endpoint else "recorded",
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
                    started = time.perf_counter()
                    self.send_response(HTTPStatus.OK.value)
                    self.send_header("Content-Type", "application/x-ndjson")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()

                    def emit(kind: str, payload: dict[str, Any]) -> None:
                        row = json.dumps(
                            {"type": "stage", "stage": kind, "detail": payload},
                            separators=(",", ":"),
                        ).encode("utf-8") + b"\n"
                        self.wfile.write(row)
                        self.wfile.flush()

                    try:
                        payload = build_surgedesk_payload(ROOT, on_audit_stage=emit)
                        receipt = _audit_receipt(
                            payload, (time.perf_counter() - started) * 1000
                        )
                        terminal = {"type": "result", "receipt": receipt}
                    except (OSError, ValueError) as exc:
                        terminal = {"type": "error", "error": str(exc)}
                    self.wfile.write(json.dumps(
                        terminal,
                        separators=(",", ":"),
                    ).encode("utf-8") + b"\n")
                    self.wfile.flush()
                    self.close_connection = True
                    return
                if self.path == "/api/audit":
                    started = time.perf_counter()
                    payload = build_surgedesk_payload(ROOT)
                    self._json(
                        HTTPStatus.OK,
                        _audit_receipt(
                            payload, (time.perf_counter() - started) * 1000
                        ),
                    )
                    return
                if self.path == "/api/scaffold-preview":
                    with tempfile.TemporaryDirectory() as directory:
                        output = Path(directory) / "my-arm-service"
                        create_scaffold(output, "http://127.0.0.1:8000/infer")
                        files = sorted(
                            path.relative_to(output).as_posix()
                            for path in output.rglob("*")
                            if path.is_file()
                        )
                    self._json(
                        HTTPStatus.OK,
                        {
                            "command": (
                                "armproof init --endpoint "
                                "http://127.0.0.1:8000/infer --output my-arm-service"
                            ),
                            "files": files,
                            "next": (
                                "The CLI writes these files to the selected directory. "
                                "Collect declared evidence next; CI blocks until "
                                "evidence/SHA256SUMS exists."
                            ),
                        },
                    )
                    return
                if self.path == "/api/tamper-check":
                    archive = ROOT / "ops/evidence/EXP-2026-009/evidence.tar.gz"
                    expected_digest = (
                        "f22e647aabe40eefd2abc5548306f40e2a5558ce1a85bc31c18319e6e51d78da"
                    )
                    started = time.perf_counter()
                    with tempfile.TemporaryDirectory() as directory:
                        altered = Path(directory) / "altered-evidence.tar.gz"
                        content = bytearray(archive.read_bytes())
                        content[-1] ^= 1
                        altered.write_bytes(content)
                        observed_digest = hashlib.sha256(content).hexdigest()
                        contract = parse_contract(json.loads((
                            ROOT / "examples/armproof-reference/sustained-contract.json"
                        ).read_text(encoding="utf-8")))
                        try:
                            derive_sustained_audit(
                                altered,
                                expected_sha256=expected_digest,
                                contract=contract,
                                workload_manifest=(
                                    ROOT / "data/banking77/generated/manifest.json"
                                ),
                            )
                        except ValueError as exc:
                            if "digest" not in str(exc).lower():
                                raise
                        else:
                            self._json(
                                HTTPStatus.INTERNAL_SERVER_ERROR,
                                {"error": "altered_archive_was_not_blocked"},
                            )
                            return
                    self._json(
                        HTTPStatus.OK,
                        {
                            "decision": "BLOCK",
                            "reason": "archive_digest_mismatch",
                            "expected_sha256": expected_digest,
                            "observed_sha256": observed_digest,
                            "mutation": "one byte changed in a temporary copy",
                            "elapsed_ms": (time.perf_counter() - started) * 1000,
                        },
                    )
                    return
                if self.path == "/api/route":
                    if not route_endpoint:
                        self._json(
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            {"error": "live_endpoint_not_configured"},
                        )
                        return
                    route_config = {
                        **lanes["optimized"],
                        "endpoint": route_endpoint,
                    }
                    route_probe = _probe_lane(route_config)
                    if not route_probe[0]:
                        self._json(
                            HTTPStatus.CONFLICT,
                            {"error": "route_runtime_identity_changed"},
                        )
                        return
                    payload = self._body()
                    text = self._text(payload)
                    upstream, elapsed_ms, _ = _upstream_request(
                        route_endpoint,
                        text=text,
                        categories=categories,
                        request_id=f"surgedesk-{uuid.uuid4().hex[:12]}",
                        expected_backend=None,
                    )
                    if not _response_identity_matches(upstream, route_probe[2]):
                        self._json(
                            HTTPStatus.CONFLICT,
                            {"error": "route_inference_identity_mismatch"},
                        )
                        return
                    result = compose_live_route(text, upstream, guard, categories)
                    result["gateway_latency_ms"] = elapsed_ms
                    self._json(HTTPStatus.OK, result)
                    return
                if self.path.startswith("/api/surge/"):
                    lane = self.path.rsplit("/", 1)[-1]
                    lane_config = lanes.get(lane)
                    if not lane_config:
                        self._json(HTTPStatus.NOT_FOUND, {"error": "unknown_lane"})
                        return
                    lane_endpoint = lane_config["endpoint"]
                    if not lane_endpoint:
                        self._json(
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            {"error": f"{lane}_endpoint_not_configured"},
                        )
                        return
                    lane_probes = {
                        name: _probe_lane(config) for name, config in lanes.items()
                    }
                    matched, reason, live_identity = _match_lane_identity(
                        lane_probes["baseline"], lane_probes["optimized"]
                    )
                    if not matched:
                        self._json(
                            HTTPStatus.CONFLICT,
                            {"error": "runtime_identity_changed", "detail": reason},
                        )
                        return
                    payload = self._body()
                    text = self._text(payload)
                    run_id = payload.get("run_id")
                    sequence = payload.get("sequence")
                    if (
                        not isinstance(run_id, str)
                        or not run_id.isalnum()
                        or not isinstance(sequence, int)
                        or sequence not in {1, 2, 3}
                    ):
                        raise ValueError("run_id and sequence are invalid")
                    request_id = f"surge-{run_id}-{sequence}"
                    upstream, elapsed_ms, started_at = _upstream_request(
                        str(lane_endpoint),
                        text=text,
                        categories=categories,
                        request_id=request_id,
                        expected_backend=str(lane_config["expected_backend"]),
                    )
                    expected_health = lane_probes[lane][2]
                    if not _response_identity_matches(upstream, expected_health):
                        self._json(
                            HTTPStatus.CONFLICT,
                            {"error": "inference_identity_mismatch"},
                        )
                        return
                    route = compose_live_route(text, upstream, guard, categories)
                    self._json(
                        HTTPStatus.OK,
                        {
                            **route,
                            "lane": lane,
                            "lane_label": lane_config["label"],
                            "sequence": sequence,
                            "request_id": request_id,
                            "core_group": lane_config["core_group"],
                            "gateway_started_at": started_at,
                            "gateway_latency_ms": elapsed_ms,
                            "runtime_identity": live_identity,
                        },
                    )
                    return
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except (urllib.error.URLError, TimeoutError) as exc:
                self._json(HTTPStatus.BAD_GATEWAY, {"error": type(exc).__name__})

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--endpoint", default=os.environ.get("SURGEDESK_INFERENCE_ENDPOINT"))
    parser.add_argument(
        "--baseline-endpoint", default=os.environ.get("SURGEDESK_BASELINE_ENDPOINT")
    )
    parser.add_argument(
        "--optimized-endpoint", default=os.environ.get("SURGEDESK_OPTIMIZED_ENDPOINT")
    )
    parser.add_argument("--baseline-cores", default="0-7")
    parser.add_argument("--optimized-cores", default="8-15")
    args = parser.parse_args()
    print(f"SurgeDesk: http://{args.host}:{args.port}/surgedesk/")
    print(
        "Live route: "
        f"{'configured; enabled after runtime identity probe' if args.endpoint or args.optimized_endpoint else 'disabled'}"
    )
    print(
        "Matched request check: "
        f"{'configured; enabled after matched identity probes' if args.baseline_endpoint and args.optimized_endpoint else 'disabled'}"
    )
    ThreadingHTTPServer(
        (args.host, args.port),
        handler_for(
            args.endpoint,
            baseline_endpoint=args.baseline_endpoint,
            optimized_endpoint=args.optimized_endpoint,
            baseline_cores=args.baseline_cores,
            optimized_cores=args.optimized_cores,
        ),
    ).serve_forever()


if __name__ == "__main__":
    main()
