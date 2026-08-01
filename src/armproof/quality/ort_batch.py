"""Native ONNX Runtime GenAI batched quality evaluation."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Sequence

from armproof.quality.banking77 import QualityCase, QualityResult, evaluate_quality
from armproof.reference.phi4 import CHAT
from armproof.workload import RequestSample


def run_ort_batched_quality(
    model_path: Path,
    cases: Sequence[QualityCase],
    *,
    batch_size: int = 4,
    label: str,
) -> tuple[QualityResult, list[RequestSample]]:
    """Generate all quality rows through the pinned runtime's native batch API."""
    if not cases:
        raise ValueError("quality cases cannot be empty")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    import onnxruntime_genai as og

    model = og.Model(str(model_path))
    tokenizer = og.Tokenizer(model)
    samples: list[RequestSample] = []
    for offset in range(0, len(cases), batch_size):
        batch = cases[offset : offset + batch_size]
        prompts = [CHAT.format(case.request.payload["prompt"]) for case in batch]
        requested_tokens = {case.request.payload.get("max_new_tokens", 32) for case in batch}
        if len(requested_tokens) != 1:
            raise ValueError("each quality batch must have one max_new_tokens value")
        max_new_tokens = requested_tokens.pop()
        prompt_lengths = [len(tokenizer.encode(prompt)) for prompt in prompts]
        padded_prompt_length = max(prompt_lengths)
        params = og.GeneratorParams(model)
        params.set_search_options(
            batch_size=len(batch),
            do_sample=False,
            max_length=padded_prompt_length + max_new_tokens,
            top_k=1,
        )
        generator = og.Generator(model, params)
        started_ns = time.monotonic_ns()
        generator.append_tokens(tokenizer.encode_batch(prompts))
        while not generator.is_done():
            generator.generate_next_token()
        finished_ns = time.monotonic_ns()
        for index, case in enumerate(batch):
            sequence = list(generator.get_sequence(index))
            generated = sequence[padded_prompt_length:]
            samples.append(
                RequestSample(
                    request_id=case.request.request_id,
                    scheduled_ns=started_ns,
                    started_ns=started_ns,
                    finished_ns=finished_ns,
                    status_code=200,
                    error=None,
                    response={
                        "request_id": case.request.request_id,
                        "output": tokenizer.decode(generated),
                        "prompt_tokens": prompt_lengths[index],
                        "output_tokens": len(generated),
                        "backend": label,
                    },
                )
            )
    return evaluate_quality(cases, samples), samples
