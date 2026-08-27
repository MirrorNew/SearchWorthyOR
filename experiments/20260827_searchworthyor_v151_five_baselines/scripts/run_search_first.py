from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from common import EXPERIMENT_ROOT, load_config, selected_ids, validate_formal_gate, write_json
from gated_search_pipeline import run_case, validate_search_budget


METHOD = "Search-First Gated Raw-NL"
METHOD_SLUG = "search_first"


def method_root(phase: str) -> Path:
    return EXPERIMENT_ROOT / "runs" / phase / METHOD_SLUG


def run_one(phase: str, task_id: str) -> dict[str, Any]:
    return run_case("search_first", phase, task_id, METHOD, METHOD_SLUG)


def summary(phase: str, ids: list[str]) -> dict[str, Any]:
    outputs = []
    root = method_root(phase)
    for task_id in ids:
        path = root / task_id / "unified_output.json"
        if path.is_file():
            outputs.append(json.loads(path.read_text(encoding="utf-8")))
    status_counts: dict[str, int] = {}
    retrieval_counts: dict[str, int] = {}
    gate_counts: dict[str, int] = {}
    final_solve_counts: dict[str, int] = {}
    for output in outputs:
        for target, value in (
            (status_counts, output.get("status")),
            (retrieval_counts, output.get("retrieval_status")),
            (gate_counts, (output.get("search_gate") or {}).get("status")),
            (final_solve_counts, (output.get("final_solve") or {}).get("status")),
        ):
            key = str(value)
            target[key] = target.get(key, 0) + 1
    return {
        "method": METHOD,
        "phase": phase,
        "expected": len(ids),
        "completed": len(outputs),
        "answer_present": sum(output.get("answer_present") is True for output in outputs),
        "raw_nl_nonempty": sum(bool(output.get("retrieved_evidence_raw_nl")) for output in outputs),
        "status_counts": status_counts,
        "search_gate_status_counts": gate_counts,
        "retrieval_status_counts": retrieval_counts,
        "final_solve_status_counts": final_solve_counts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run V1.5.1 Search-First Gated Raw-NL")
    parser.add_argument("--phase", choices=["smoke", "formal"], required=True)
    parser.add_argument("--task-ids", default="")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    load_config()
    validate_search_budget(0)
    if args.phase == "formal":
        if args.task_ids:
            raise SystemExit("Formal Search-First must run all fixed 240 cases; subsets are forbidden")
        validate_formal_gate()
    if not 1 <= args.workers <= 10:
        raise SystemExit("Search-First workers must be between 1 and 10")
    ids = selected_ids(args.phase, args.task_ids)
    root = method_root(args.phase)
    root.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(run_one, args.phase, task_id): task_id for task_id in ids}
        for completed, future in enumerate(as_completed(futures), start=1):
            task_id = futures[future]
            future.result()
            current = summary(args.phase, ids)
            write_json(root / "summary.json", current)
            print(json.dumps({"completed_now": completed, "task_id": task_id, **current}, ensure_ascii=False), flush=True)
    final = summary(args.phase, ids)
    write_json(root / "summary.json", final)
    print(json.dumps(final, ensure_ascii=False))
    return 0 if final["completed"] == len(ids) else 1


if __name__ == "__main__":
    raise SystemExit(main())
