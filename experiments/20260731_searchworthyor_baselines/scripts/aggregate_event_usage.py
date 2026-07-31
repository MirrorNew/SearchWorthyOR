from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)


def read_turn_usage(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: {exc}") from exc
        if event.get("type") == "turn.completed":
            rows.append(event.get("usage") or {})
    return rows


def task_id_for(path: Path, root: Path) -> str:
    for part in path.relative_to(root).parts:
        if part.startswith("SWOR"):
            return part
    return "unattributed"


def stage_for(path: Path) -> str:
    name = path.name
    if name in {"events.jsonl", "codex_events.jsonl"}:
        return "final"
    if name.endswith(".events.jsonl"):
        return name[: -len(".events.jsonl")]
    return name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    totals: Counter[str] = Counter()
    by_stage: dict[str, Counter[str]] = defaultdict(Counter)
    calls_by_task: Counter[str] = Counter()
    files_with_usage = []
    files_without_usage = []
    duplicate_turn_files = []

    event_files = sorted(args.run_root.rglob("*events.jsonl"))
    for path in event_files:
        usages = read_turn_usage(path)
        if not usages:
            files_without_usage.append(
                path.relative_to(args.run_root).as_posix()
            )
            continue
        if len(usages) > 1:
            duplicate_turn_files.append(
                {
                    "path": path.relative_to(args.run_root).as_posix(),
                    "turn_completed_count": len(usages),
                }
            )
        files_with_usage.append(path.relative_to(args.run_root).as_posix())
        stage = stage_for(path)
        task_id = task_id_for(path, args.run_root)
        for usage in usages:
            totals["model_calls"] += 1
            by_stage[stage]["model_calls"] += 1
            calls_by_task[task_id] += 1
            for field in TOKEN_FIELDS:
                value = int(usage.get(field) or 0)
                totals[field] += value
                by_stage[stage][field] += value

    payload = {
        "run_root": str(args.run_root.resolve()),
        "event_file_count": len(event_files),
        "files_with_usage_count": len(files_with_usage),
        "files_without_usage_count": len(files_without_usage),
        "duplicate_turn_files": duplicate_turn_files,
        "totals": dict(totals),
        "by_stage": {
            stage: dict(values)
            for stage, values in sorted(by_stage.items())
        },
        "calls_by_task": dict(sorted(calls_by_task.items())),
        "task_count_with_usage": len(calls_by_task),
        "files_without_usage": files_without_usage,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "event_files": payload["event_file_count"],
                "files_with_usage": payload["files_with_usage_count"],
                "files_without_usage": payload[
                    "files_without_usage_count"
                ],
                "task_count_with_usage": payload[
                    "task_count_with_usage"
                ],
                "totals": payload["totals"],
                "duplicate_turn_files": duplicate_turn_files,
            },
            ensure_ascii=False,
        )
    )
    return 0 if not duplicate_turn_files else 1


if __name__ == "__main__":
    raise SystemExit(main())
