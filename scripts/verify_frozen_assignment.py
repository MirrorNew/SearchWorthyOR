#!/usr/bin/env python3
"""Verify a candidate patch assignment without rebuilding release artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from audit_duplicates_and_leakage import metadata_decoder_audit
from build_dataset import public_task_id


ROOT = Path(__file__).resolve().parents[1]
PATCH_CLASSES = (
    "eligibility_domain",
    "temporal_coupling",
    "conditional_auxiliary",
    "quota_risk_service_objective",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def verify_assignment(ordinals: str) -> dict[str, Any]:
    if len(ordinals) != 100 or any(value not in "0123" for value in ordinals):
        raise ValueError("assignment must contain exactly 100 ordinals in 0..3")
    labels = [PATCH_CLASSES[int(value)] for value in ordinals]
    counts = Counter(labels)
    expected = Counter({label: 25 for label in PATCH_CLASSES})
    if counts != expected:
        raise ValueError(f"assignment is not globally balanced: {dict(counts)}")
    web_mismatches = [
        {
            "internal_index": index,
            "expected_ordinal": index % 4,
            "actual_ordinal": int(ordinals[index]),
        }
        for index in range(100)
        if index % 10 >= 8 and int(ordinals[index]) != index % 4
    ]
    if web_mismatches:
        raise ValueError(
            "assignment changes the frozen web source-to-patch semantics: "
            f"{web_mismatches}"
        )

    tasks = load_jsonl(ROOT / "public" / "tasks_zh.jsonl")
    if len(tasks) != 100:
        raise ValueError(f"expected 100 public tasks, found {len(tasks)}")
    label_by_task_id = {
        public_task_id(index): label for index, label in enumerate(labels)
    }
    task_ids = {str(task["id"]) for task in tasks}
    if task_ids != set(label_by_task_id):
        raise ValueError("public task IDs do not match the deterministic ID map")
    synthetic_gold = [
        {"id": task["id"], "patch_class": label_by_task_id[str(task["id"])]}
        for task in tasks
    ]
    audit = metadata_decoder_audit(tasks, synthetic_gold)
    return {
        "assignment": ordinals,
        "class_counts": dict(sorted(counts.items())),
        "web_semantics_preserved": True,
        "metadata_decoder": audit,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ordinals", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_assignment(args.ordinals)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["metadata_decoder"].get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
