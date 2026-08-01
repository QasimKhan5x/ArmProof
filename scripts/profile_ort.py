#!/usr/bin/env python3
"""Generate sustained pinned-runtime work for an external callchain profiler."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from armproof.reference.phi4 import CHAT


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--workload", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    import onnxruntime_genai as og

    model = og.Model(str(args.model))
    tokenizer = og.Tokenizer(model)
    rows = [json.loads(line) for line in args.workload.read_text().splitlines() if line.strip()][:4]
    prompts = [CHAT.format(row["payload"]["prompt"]) for row in rows]
    lengths = [len(tokenizer.encode(prompt)) for prompt in prompts]
    for _ in range(args.repetitions):
        params = og.GeneratorParams(model)
        params.set_search_options(
            batch_size=len(prompts), do_sample=False, max_length=max(lengths) + 64, top_k=1
        )
        generator = og.Generator(model, params)
        generator.append_tokens(tokenizer.encode_batch(prompts))
        while not generator.is_done():
            generator.generate_next_token()


if __name__ == "__main__":
    main()
