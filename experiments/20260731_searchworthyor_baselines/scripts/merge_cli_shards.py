from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--shard-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected", required=True, type=int)
    parser.add_argument("--allow-active-failures", action="store_true")
    args = parser.parse_args()

    public_rows = read_jsonl(
        args.dataset_root / "public" / "tasks_zh.jsonl"
    )
    order = {row["id"]: index for index, row in enumerate(public_rows)}
    submissions = []
    failure_rows = []
    shard_summaries = []
    for shard_dir in sorted(args.shard_root.glob("shard*")):
        rows = []
        failures = []
        for task_dir in sorted(shard_dir.glob("SWOR*")):
            submission_path = task_dir / "submission.json"
            failure_path = task_dir / "failure.json"
            if submission_path.exists():
                rows.append(
                    json.loads(
                        submission_path.read_text(encoding="utf-8-sig")
                    )
                )
            if failure_path.exists():
                failures.append(
                    json.loads(
                        failure_path.read_text(encoding="utf-8-sig")
                    )
                )
        submissions.extend(rows)
        failure_rows.extend(failures)
        shard_summaries.append(
            {
                "shard": shard_dir.name,
                "submissions": len(rows),
                "failures": failures,
            }
        )
    by_id: dict[str, dict[str, Any]] = {}
    duplicates = []
    for row in submissions:
        task_id = row["task_id"]
        if task_id in by_id:
            duplicates.append(task_id)
        by_id[task_id] = row
    unknown = sorted(set(by_id) - set(order))
    active_failures = {
        row["task_id"]: row
        for row in failure_rows
        if row.get("task_id") not in by_id
    }
    recovered_failures = [
        row for row in failure_rows if row.get("task_id") in by_id
    ]
    covered_ids = set(by_id) | set(active_failures)
    missing_submissions = sorted(set(order) - set(by_id))
    uncovered = sorted(set(order) - covered_ids)
    unknown_failures = sorted(set(active_failures) - set(order))
    merged = sorted(
        by_id.values(), key=lambda row: order[row["task_id"]]
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False) + "\n"
            for row in merged
        ),
        encoding="utf-8",
    )
    audit = {
        "expected": args.expected,
        "merged": len(merged),
        "duplicates": sorted(set(duplicates)),
        "unknown": unknown,
        "missing_submissions": missing_submissions,
        "active_failures": [
            active_failures[task_id] for task_id in sorted(active_failures)
        ],
        "recovered_failure_count": len(recovered_failures),
        "uncovered": uncovered,
        "unknown_failures": unknown_failures,
        "shards": shard_summaries,
        "passed": (
            len(covered_ids) == args.expected
            and not duplicates
            and not unknown
            and not unknown_failures
            and not uncovered
            and (
                args.allow_active_failures
                or not active_failures
            )
        ),
    }
    audit_path = args.output.with_suffix(".merge_audit.json")
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit, ensure_ascii=False))
    return 0 if audit["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
