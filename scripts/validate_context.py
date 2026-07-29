#!/usr/bin/env python3
"""Validate durable project context without third-party dependencies."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot parse {path.relative_to(ROOT)}: {exc}")


def validate_required_files() -> None:
    required = [
        "README.md",
        "AGENTS.md",
        "STATUS.md",
        "docs/PROJECT_MAP.md",
        "docs/CONCEPT.md",
        "docs/REQUIREMENTS.md",
        "docs/JUDGING_STRATEGY.md",
        "docs/FEASIBILITY_PLAN.md",
        "docs/ARCHITECTURE.md",
        "docs/BENCHMARK_PROTOCOL.md",
        "docs/ROADMAP.md",
        "docs/AWS_BUDGET.md",
        "docs/RISKS.md",
        "docs/TRACEABILITY.md",
        "docs/AGENT_PLAYBOOK.md",
        "docs/DEMO_AND_SUBMISSION.md",
        "docs/SECURITY_AND_LICENSES.md",
        "docs/DECISIONS.md",
        "docs/SOURCES.md",
        "ops/work-items.json",
        "schemas/experiment.schema.json",
    ]
    missing = [item for item in required if not (ROOT / item).is_file()]
    if missing:
        fail(f"missing required files: {', '.join(missing)}")


def validate_links() -> None:
    for path in ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            clean_target = target.split("#", 1)[0]
            if not clean_target:
                continue
            resolved = (path.parent / clean_target).resolve()
            if not resolved.exists():
                fail(
                    f"broken link in {path.relative_to(ROOT)}: {target}"
                )


def validate_work_items() -> None:
    payload = load_json(ROOT / "ops/work-items.json")
    if not isinstance(payload, dict):
        fail("ops/work-items.json must contain an object")

    allowed = set(payload.get("allowed_statuses", []))
    items = payload.get("items", [])
    if not isinstance(items, list) or not items:
        fail("ops/work-items.json must contain work items")

    by_id: dict[str, dict[str, object]] = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            fail("every work item must have a string id")
        item_id = item["id"]
        if item_id in by_id:
            fail(f"duplicate work item id: {item_id}")
        if item.get("status") not in allowed:
            fail(f"invalid status for {item_id}: {item.get('status')}")
        by_id[item_id] = item

    for item_id, item in by_id.items():
        for dependency in item.get("dependencies", []):
            if dependency not in by_id:
                fail(f"unknown dependency for {item_id}: {dependency}")
        for context_path in item.get("context", []):
            if not (ROOT / context_path).is_file():
                fail(f"missing context for {item_id}: {context_path}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(item_id: str) -> None:
        if item_id in visiting:
            fail(f"dependency cycle includes {item_id}")
        if item_id in visited:
            return
        visiting.add(item_id)
        for dependency in by_id[item_id].get("dependencies", []):
            visit(dependency)
        visiting.remove(item_id)
        visited.add(item_id)

    for item_id in by_id:
        visit(item_id)


def validate_experiment_files() -> None:
    load_json(ROOT / "schemas/experiment.schema.json")
    registry = ROOT / "ops/experiments/registry.jsonl"
    for line_number, line in enumerate(
        registry.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:
            fail(f"invalid registry JSON on line {line_number}: {exc}")


def main() -> None:
    validate_required_files()
    validate_links()
    validate_work_items()
    validate_experiment_files()
    print("Context validation passed.")


if __name__ == "__main__":
    main()
