#!/usr/bin/env python3
"""Validate ArmProof's durable context without third-party dependencies."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
TASK_ID_RE = re.compile(r"\*\*([A-Z]+-[0-9]+):")
WORK_REF_RE = re.compile(r"\b[A-Z]{3,}-[0-9]{3}\b")

REQUIRED_FILES = [
    "README.md",
    "AGENTS.md",
    "STATUS.md",
    "docs/DEVELOPMENT.md",
    "docs/QUICKSTART.md",
    "docs/PROJECT_MAP.md",
    "docs/PRODUCT_SPEC.md",
    "docs/CONCEPT.md",
    "docs/REQUIREMENTS.md",
    "docs/JUDGING_STRATEGY.md",
    "docs/ESTABLISHED_EVIDENCE.md",
    "docs/CAPACITY_VALIDATION.md",
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
    "docs/GLOSSARY.md",
    "tasks/plan.md",
    "tasks/todo.md",
    "context/README.md",
    "context/packs/EVID-001.md",
    "context/packs/CAP-001.md",
    "context/packs/TEMPLATE.md",
    "ops/work-items.json",
    "schemas/contract.schema.json",
    "schemas/ci-config.schema.json",
    "schemas/comparison.schema.json",
    "schemas/decision.schema.json",
    "schemas/evidence-manifest.schema.json",
    "schemas/experiment.schema.json",
]

# These terms belong only in explicit historical records. Their presence in
# active instructions is a strong signal that an agent received stale context.
RETIRED_TERMS = {
    "KleidiScope": {"docs/DECISIONS.md"},
    "target-bpw": {"docs/DECISIONS.md"},
    "SRC-001": set(),
}
IGNORED_LINK_DIRS = {".git", ".venv", "build", "dist", "node_modules", "test-results"}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot parse {path.relative_to(ROOT)}: {exc}")


def validate_required_files() -> None:
    missing = [item for item in REQUIRED_FILES if not (ROOT / item).is_file()]
    if missing:
        fail(f"missing required files: {', '.join(missing)}")


def validate_links() -> None:
    for path in ROOT.rglob("*.md"):
        if IGNORED_LINK_DIRS.intersection(path.relative_to(ROOT).parts):
            continue
        text = path.read_text(encoding="utf-8")
        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            clean_target = target.split("#", 1)[0]
            if not clean_target:
                continue
            if not (path.parent / clean_target).resolve().exists():
                fail(f"broken link in {path.relative_to(ROOT)}: {target}")


def validate_work_items() -> dict[str, dict[str, object]]:
    payload = load_json(ROOT / "ops/work-items.json")
    if not isinstance(payload, dict):
        fail("ops/work-items.json must contain an object")

    allowed = set(payload.get("allowed_statuses", []))
    spec_gate = payload.get("spec_gate")
    items = payload.get("items")
    if not isinstance(spec_gate, dict):
        fail("ops/work-items.json must define spec_gate")
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
        if not item.get("verification"):
            fail(f"work item has no verification layer: {item_id}")
        by_id[item_id] = item

    for item_id, item in by_id.items():
        dependencies = item.get("dependencies", [])
        context_paths = item.get("context", [])
        if not isinstance(dependencies, list) or not isinstance(context_paths, list):
            fail(f"dependencies and context must be arrays for {item_id}")
        for dependency in dependencies:
            if dependency not in by_id:
                fail(f"unknown dependency for {item_id}: {dependency}")
        for context_path in context_paths:
            if not isinstance(context_path, str) or not (ROOT / context_path).is_file():
                fail(f"missing context for {item_id}: {context_path}")
        packs = [path for path in context_paths if path.startswith("context/packs/")]
        if packs and len(context_paths) != 1:
            fail(f"{item_id} must reference only its focused context pack")

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

    gate_item = spec_gate.get("work_item")
    if gate_item not in by_id:
        fail(f"spec gate references unknown work item: {gate_item}")
    if spec_gate.get("status") != "approved":
        fail("ArmProof product spec must be approved before implementation")
    if by_id[gate_item].get("status") != "completed":
        fail("approved spec gate work item must be completed")

    return by_id


def validate_task_index(by_id: dict[str, dict[str, object]]) -> None:
    todo = (ROOT / "tasks/todo.md").read_text(encoding="utf-8")
    task_ids = TASK_ID_RE.findall(todo)
    if len(task_ids) != len(set(task_ids)):
        fail("tasks/todo.md contains duplicate task IDs")
    missing = sorted(set(by_id) - set(task_ids))
    extra = sorted(set(task_ids) - set(by_id))
    if missing or extra:
        fail(f"task index disagrees with work items; missing={missing}, extra={extra}")

    routing_files = [
        ROOT / "STATUS.md",
        ROOT / "tasks/plan.md",
        ROOT / "docs/TRACEABILITY.md",
        *(ROOT / "context/packs").glob("*.md"),
    ]
    for path in routing_files:
        for work_ref in WORK_REF_RE.findall(path.read_text(encoding="utf-8")):
            if work_ref not in by_id:
                fail(
                    f"unknown work-item reference {work_ref} in "
                    f"{path.relative_to(ROOT)}"
                )


def validate_experiment_files() -> None:
    schema = load_json(ROOT / "schemas/experiment.schema.json")
    if not isinstance(schema, dict) or schema.get("title") != "ArmProof Experiment Record":
        fail("experiment schema is not the current ArmProof schema")

    registry = ROOT / "ops/experiments/registry.jsonl"
    if not registry.is_file():
        fail("missing ops/experiments/registry.jsonl")
    for line_number, line in enumerate(
        registry.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            fail(f"invalid registry JSON on line {line_number}: {exc}")
        if not isinstance(record, dict) or "record_type" not in record:
            fail(f"registry line {line_number} lacks record_type")


def validate_context_budgets() -> None:
    limits = {ROOT / "AGENTS.md": 120, ROOT / "STATUS.md": 100}
    for pack in (ROOT / "context/packs").glob("*.md"):
        limits[pack] = 150
    for path, limit in limits.items():
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > limit:
            fail(f"{path.relative_to(ROOT)} exceeds context limit {limit}: {line_count}")

    spec = (ROOT / "docs/PRODUCT_SPEC.md").read_text(encoding="utf-8")
    if "Status: **APPROVED**" not in spec or "Version: **1.0.0**" not in spec:
        fail("product spec approval block is missing or stale")


def validate_retired_terms() -> None:
    scan_paths = [ROOT / item for item in REQUIRED_FILES if item.endswith(".md")]
    scan_paths.extend([ROOT / "ops/work-items.json", ROOT / "tasks/todo.md"])
    for path in dict.fromkeys(scan_paths):
        relative = str(path.relative_to(ROOT))
        text = path.read_text(encoding="utf-8")
        for term, exemptions in RETIRED_TERMS.items():
            if term in text and relative not in exemptions:
                fail(f"retired term {term!r} remains in active context: {relative}")


def main() -> None:
    validate_required_files()
    validate_links()
    work_items = validate_work_items()
    validate_task_index(work_items)
    validate_experiment_files()
    validate_context_budgets()
    validate_retired_terms()
    print("Context validation passed.")


if __name__ == "__main__":
    main()
