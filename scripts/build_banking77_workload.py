#!/usr/bin/env python3
"""Build deterministic ArmProof quality and traffic sets from BANKING77."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data/banking77"
SOURCE_ROOT = DATA_ROOT / "source"
OUTPUT_ROOT = DATA_ROOT / "generated"
UPSTREAM_COMMIT = "57ec275d8078af65b7731c2a98be812d844a6d6b"
SOURCE_HASHES = {
    "categories.json": "53261da888122daf2d120d925458631d9619e15d82e56052e7a42e535ce32b63",
    "test.csv": "d12d6e3bc4c3103966ae786dc435913c0c563dfa328f5a3646d0e62cfeeb474d",
    "LICENSE-CC-BY-4.0": "7e7170e3cebf88a9f60c7b8421418323c09304da1af4d5e90f4da1dc1c8a2661",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def prompt(text: str, categories: list[str], detailed: bool) -> str:
    labels = ", ".join(categories)
    if detailed:
        instruction = (
            'Return only JSON with keys "intent", "urgency", and "rationale". '
            'Intent must be one valid label, urgency must be "low", "medium", or "high", '
            "and rationale must be one sentence."
        )
    else:
        instruction = 'Return only JSON in this form: {"intent":"one_valid_label"}.'
    return (
        "Route this online-banking support request.\n"
        f"Valid intent labels: {labels}\n"
        f"{instruction}\n"
        f"Customer request: {text}"
    )


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def workload_row(index: int, text: str, categories: list[str], detailed: bool, prefix: str) -> dict:
    request_id = f"banking77-{prefix}-{index:04d}"
    return {
        "request_id": request_id,
        "payload": {
            "request_id": request_id,
            "prompt": prompt(text, categories, detailed),
            "max_new_tokens": 96 if detailed else 32,
        },
    }


def main() -> None:
    for filename, expected in SOURCE_HASHES.items():
        observed = digest(SOURCE_ROOT / filename)
        if observed != expected:
            raise SystemExit(f"source hash mismatch for {filename}: {observed}")
    categories = json.loads((SOURCE_ROOT / "categories.json").read_text(encoding="utf-8"))
    with (SOURCE_ROOT / "test.csv").open(encoding="utf-8", newline="") as stream:
        source_rows = list(csv.DictReader(stream))
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in source_rows:
        grouped[row["category"]].append(row)
    if set(grouped) != set(categories) or any(len(grouped[item]) != 40 for item in categories):
        raise SystemExit("BANKING77 test split no longer has 40 examples for every category")

    quality = []
    quality_index = 0
    for category in categories:
        for source in grouped[category][:10]:
            base = workload_row(quality_index, source["text"], categories, False, "quality")
            quality.append({**base, "expected_intent": category, "source_text": source["text"]})
            quality_index += 1

    ordered = sorted(source_rows, key=lambda row: (len(row["text"]), stable_key(row["text"])))
    short_sources = ordered[:512]
    long_sources = sorted(source_rows, key=lambda row: stable_key("long\0" + row["text"]))[:512]
    short = [
        workload_row(index, row["text"], categories, False, "short")
        for index, row in enumerate(short_sources)
    ]
    long = [
        workload_row(index, row["text"], categories, True, "long")
        for index, row in enumerate(long_sources)
    ]
    mixed = []
    for index in range(512):
        source = short_sources[index] if index % 2 == 0 else long_sources[index]
        mixed.append(workload_row(index, source["text"], categories, index % 2 == 1, "mixed"))

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    outputs = {
        "quality.jsonl": quality,
        "traffic-short.jsonl": short,
        "traffic-long.jsonl": long,
        "traffic-mixed.jsonl": mixed,
    }
    for filename, rows in outputs.items():
        write_jsonl(OUTPUT_ROOT / filename, rows)
    manifest = {
        "schema_version": "1.0.0",
        "dataset": "BANKING77",
        "upstream_repository": "https://github.com/PolyAI-LDN/task-specific-datasets",
        "upstream_commit": UPSTREAM_COMMIT,
        "license": "CC-BY-4.0",
        "source_hashes": SOURCE_HASHES,
        "outputs": {
            filename: {"rows": len(rows), "sha256": digest(OUTPUT_ROOT / filename)}
            for filename, rows in outputs.items()
        },
        "categories": len(categories),
        "selection": "first 10 test examples per upstream category for quality; deterministic traffic transforms",
    }
    (OUTPUT_ROOT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest["outputs"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
