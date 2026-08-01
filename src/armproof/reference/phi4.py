"""Common HTTP service for the pinned Phi-4 BF16 and ORT GenAI INT4 paths."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol


CHAT = "<|user|>{}<|end|><|assistant|>"
MAX_BODY_BYTES = 1024 * 1024


class Backend(Protocol):
    label: str

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
    except Exception:
        shutil.rmtree(destination)
        raise
    return destination


class OrtInt4Backend:
    def __init__(self, model_path: Path, label: str) -> None:
        import onnxruntime_genai as og

        self.og = og
        self.model = og.Model(str(model_path))
        self.tokenizer = og.Tokenizer(self.model)
        self.label = label

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
            self._json(HTTPStatus.OK, {"ready": True, "backend": backend.label})

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
    args = parser.parse_args()
    if args.threads < 1 or args.max_inflight < 1:
        parser.error("threads and max-inflight must be positive")
    if args.backend == "ort-int4":
        backend: Backend = OrtInt4Backend(args.model, args.label or "ort-int4")
    else:
        backend = PytorchBf16Backend(args.model, args.threads)
    ThreadingHTTPServer(
        (args.host, args.port),
        handler_for(backend, args.max_inflight),
    ).serve_forever()


if __name__ == "__main__":
    main()
