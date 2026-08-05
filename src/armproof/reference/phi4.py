"""Common HTTP service for the pinned Phi-4 BF16 and ORT GenAI INT4 paths."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import threading
import time
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol

from armproof.artifacts import fingerprint_path

CHAT = "<|user|>{}<|end|><|assistant|>"
MAX_BODY_BYTES = 1024 * 1024


class Backend(Protocol):
    label: str
    health_metadata: dict[str, Any]

    def generate(self, prompt: str, max_new_tokens: int) -> dict[str, Any]: ...


def create_ort_variant(source: Path, destination: Path, enabled: bool, threads: int) -> Path:
    """Create a symlink overlay changing only the declared KleidiAI control."""
    if destination.exists():
        raise FileExistsError(f"variant destination already exists: {destination}")
    if threads < 1:
        raise ValueError("threads must be positive")
    config_path = source / "genai_config.json"
    if not config_path.is_file():
        raise FileNotFoundError(config_path)
    destination.mkdir(parents=True)
    try:
        source_identity = fingerprint_path(source)
        for item in source.iterdir():
            target = destination / item.name
            if item.name == "genai_config.json":
                config = json.loads(item.read_text(encoding="utf-8"))
                options = config["model"]["decoder"].setdefault("session_options", {})
                options["intra_op_num_threads"] = threads
                options["mlas.disable_kleidiai"] = "0" if enabled else "1"
                target.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
            else:
                target.symlink_to(item.resolve())
        (destination / "armproof_source_identity.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "source_artifact_sha256": source_identity.sha256,
                    "source_path": str(source.resolve()),
                    "source_files": source_identity.files,
                    "source_bytes": source_identity.bytes,
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
    except Exception:
        shutil.rmtree(destination)
        raise
    return destination


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _aws_instance_type(timeout: float = 2.0) -> str:
    """Read the instance type from AWS IMDSv2 rather than a caller-supplied label."""
    token_request = urllib.request.Request(
        "http://169.254.169.254/latest/api/token",
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
        method="PUT",
    )
    with urllib.request.urlopen(token_request, timeout=timeout) as response:
        token = response.read().decode("utf-8").strip()
    if not token:
        raise ValueError("AWS IMDSv2 returned an empty token")
    metadata_request = urllib.request.Request(
        "http://169.254.169.254/latest/meta-data/instance-type",
        headers={"X-aws-ec2-metadata-token": token},
    )
    with urllib.request.urlopen(metadata_request, timeout=timeout) as response:
        instance_type = response.read().decode("utf-8").strip()
    if not instance_type:
        raise ValueError("AWS IMDSv2 returned an empty instance type")
    return instance_type


def _verify_runtime_artifact_ledger(path: Path) -> str:
    """Verify the pinned runtime artifacts and return the ledger digest."""
    if not path.is_file():
        raise FileNotFoundError(path)
    entries = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64:
            raise ValueError("runtime artifact ledger is malformed")
        expected, relative = parts
        artifact = (path.parent / relative.strip()).resolve()
        if not artifact.is_relative_to(path.parent.resolve()):
            raise ValueError("runtime artifact ledger escapes its directory")
        if not artifact.is_file() or _sha256_file(artifact) != expected:
            raise ValueError(f"runtime artifact checksum mismatch: {relative.strip()}")
        entries += 1
    if entries == 0:
        raise ValueError("runtime artifact ledger is empty")
    return _sha256_file(path)


def _model_item_fingerprint(path: Path) -> dict[str, Any]:
    if path.is_file():
        return {
            "kind": "file",
            "bytes": path.stat().st_size,
            "files": 1,
            "sha256": _sha256_file(path),
        }
    if not path.is_dir():
        raise FileNotFoundError(path)
    digest = hashlib.sha256(b"armproof-model-directory-v1\0")
    total_bytes = 0
    file_count = 0
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        relative = item.relative_to(path).as_posix().encode("utf-8")
        size = item.stat().st_size
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(size.to_bytes(8, "big"))
        digest.update(bytes.fromhex(_sha256_file(item)))
        total_bytes += size
        file_count += 1
    return {
        "kind": "directory",
        "bytes": total_bytes,
        "files": file_count,
        "sha256": digest.hexdigest(),
    }


def _ort_model_identity(model_path: Path) -> tuple[str, str, str, int]:
    """Identify matched variants while excluding only the declared control."""
    config_path = model_path / "genai_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    normalized = json.loads(json.dumps(config))
    options = normalized["model"]["decoder"]["session_options"]
    control = str(options.pop("mlas.disable_kleidiai"))
    threads = int(options["intra_op_num_threads"])
    source_identity = json.loads(
        (model_path / "armproof_source_identity.json").read_text(encoding="utf-8")
    )
    source_artifact_sha256 = source_identity.get("source_artifact_sha256")
    if (
        not isinstance(source_artifact_sha256, str)
        or len(source_artifact_sha256) != 64
        or any(character not in "0123456789abcdef" for character in source_artifact_sha256)
    ):
        raise ValueError("variant source artifact identity is invalid")
    source_path = source_identity.get("source_path")
    if (
        not isinstance(source_path, str)
        or fingerprint_path(Path(source_path)).sha256 != source_artifact_sha256
    ):
        raise ValueError("variant source artifact no longer matches its identity")
    files = []
    for path in sorted(model_path.iterdir(), key=lambda item: item.name):
        if path.name in {"genai_config.json", "armproof_source_identity.json"}:
            continue
        resolved = path.resolve()
        fingerprint = _model_item_fingerprint(resolved)
        files.append({
            "name": path.name,
            **fingerprint,
        })
    payload = json.dumps(
        {"config_without_control": normalized, "model_files": files},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), source_artifact_sha256, control, threads


class OrtInt4Backend:
    def __init__(
        self,
        model_path: Path,
        label: str,
        *,
        runtime_lock: Path | None = None,
        runtime_artifact_ledger: Path | None = None,
        expected_instance_type: str | None = None,
    ) -> None:
        import onnxruntime_genai as og

        model_identity, source_artifact_sha256, control, threads = _ort_model_identity(model_path)
        self.og = og
        self.model = og.Model(str(model_path))
        self.tokenizer = og.Tokenizer(self.model)
        self.label = label
        self.health_metadata = {
            "runtime": "onnxruntime-genai",
            "runtime_version": importlib.metadata.version("onnxruntime-genai"),
            "model_identity": model_identity,
            "source_artifact_sha256": source_artifact_sha256,
            "optimization_control": {"mlas.disable_kleidiai": control},
            "threads": threads,
        }
        if runtime_lock is not None:
            self.health_metadata["runtime_lock_sha256"] = _sha256_file(runtime_lock)
        if runtime_artifact_ledger is not None:
            self.health_metadata["runtime_artifact_ledger_sha256"] = (
                _verify_runtime_artifact_ledger(runtime_artifact_ledger)
            )
        if expected_instance_type is not None:
            observed_instance_type = _aws_instance_type()
            if observed_instance_type != expected_instance_type:
                raise ValueError(
                    "AWS instance type differs from the expected deployment: "
                    f"{observed_instance_type} != {expected_instance_type}"
                )
            self.health_metadata.update({
                "instance_type": observed_instance_type,
                "instance_identity_source": "aws-imdsv2",
            })

    def generate(self, prompt: str, max_new_tokens: int) -> dict[str, Any]:
        tokens = self.tokenizer.encode(CHAT.format(prompt))
        params = self.og.GeneratorParams(self.model)
        params.set_search_options(
            do_sample=False,
            max_length=len(tokens) + max_new_tokens,
            top_k=1,
        )
        generator = self.og.Generator(self.model, params)
        generator.append_tokens(tokens)
        while not generator.is_done():
            generator.generate_next_token()
        generated = list(generator.get_sequence(0))[len(tokens):]
        return {
            "output": self.tokenizer.decode(generated),
            "prompt_tokens": len(tokens),
            "output_tokens": len(generated),
        }


class PytorchBf16Backend:
    label = "pytorch-bf16"

    def __init__(self, model_path: Path, threads: int) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        torch.set_num_threads(threads)
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            dtype=torch.bfloat16,
        ).eval()
        self.health_metadata = {
            "runtime": "pytorch",
            "runtime_version": importlib.metadata.version("torch"),
            "threads": threads,
        }

    def generate(self, prompt: str, max_new_tokens: int) -> dict[str, Any]:
        inputs = self.tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
        )
        with self.torch.inference_mode():
            output = self.model.generate(
                **inputs,
                do_sample=False,
                max_new_tokens=max_new_tokens,
            )
        prompt_tokens = inputs["input_ids"].shape[-1]
        generated = output[0][prompt_tokens:]
        return {
            "output": self.tokenizer.decode(generated, skip_special_tokens=True),
            "prompt_tokens": int(prompt_tokens),
            "output_tokens": int(generated.shape[-1]),
        }


def validate_request(payload: Any) -> tuple[str, str, int]:
    if not isinstance(payload, dict):
        raise ValueError("request must be an object")
    allowed = {"request_id", "prompt", "max_new_tokens"}
    if set(payload) - allowed or not {"request_id", "prompt"} <= set(payload):
        raise ValueError("request fields must be request_id, prompt, and optional max_new_tokens")
    request_id = payload["request_id"]
    prompt = payload["prompt"]
    max_new_tokens = payload.get("max_new_tokens", 64)
    if not isinstance(request_id, str) or not request_id:
        raise ValueError("request_id must be non-empty")
    if not isinstance(prompt, str) or not prompt:
        raise ValueError("prompt must be non-empty")
    if not isinstance(max_new_tokens, int) or isinstance(max_new_tokens, bool) or not 1 <= max_new_tokens <= 512:
        raise ValueError("max_new_tokens must be between 1 and 512")
    return request_id, prompt, max_new_tokens


def handler_for(backend: Backend, max_inflight: int) -> type[BaseHTTPRequestHandler]:
    semaphore = threading.BoundedSemaphore(max_inflight)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path != "/health":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else []
            self._json(
                HTTPStatus.OK,
                {
                    "ready": True,
                    "backend": backend.label,
                    "cpu_affinity": affinity,
                    "architecture": platform.machine().lower(),
                    **backend.health_metadata,
                },
            )

        def do_POST(self) -> None:
            if self.path != "/infer":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY_BYTES:
                    raise ValueError("invalid request size")
                request_id, prompt, max_new_tokens = validate_request(
                    json.loads(self.rfile.read(length))
                )
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            queued = time.perf_counter_ns()
            with semaphore:
                started = time.perf_counter_ns()
                try:
                    result = backend.generate(prompt, max_new_tokens)
                except Exception as exc:
                    self._json(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {"request_id": request_id, "error": type(exc).__name__},
                    )
                    return
                finished = time.perf_counter_ns()
            self._json(
                HTTPStatus.OK,
                {
                    "request_id": request_id,
                    **result,
                    "queue_ms": (started - queued) / 1_000_000,
                    "inference_ms": (finished - started) / 1_000_000,
                    "backend": backend.label,
                    "runtime_identity": {
                        "cpu_affinity": (
                            sorted(os.sched_getaffinity(0))
                            if hasattr(os, "sched_getaffinity") else []
                        ),
                        "architecture": platform.machine().lower(),
                        **backend.health_metadata,
                    },
                },
            )

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("pytorch-bf16", "ort-int4"), required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--label")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--threads", type=int, default=int(os.environ.get("OMP_NUM_THREADS", "16")))
    parser.add_argument("--max-inflight", type=int, default=1)
    parser.add_argument("--runtime-lock", type=Path)
    parser.add_argument("--runtime-artifact-ledger", type=Path)
    parser.add_argument("--expected-instance-type")
    args = parser.parse_args()
    if args.threads < 1 or args.max_inflight < 1:
        parser.error("threads and max-inflight must be positive")
    if args.backend == "ort-int4":
        backend: Backend = OrtInt4Backend(
            args.model,
            args.label or "ort-int4",
            runtime_lock=args.runtime_lock,
            runtime_artifact_ledger=args.runtime_artifact_ledger,
            expected_instance_type=args.expected_instance_type,
        )
    else:
        backend = PytorchBf16Backend(args.model, args.threads)
    ThreadingHTTPServer(
        (args.host, args.port),
        handler_for(backend, args.max_inflight),
    ).serve_forever()


if __name__ == "__main__":
    main()
