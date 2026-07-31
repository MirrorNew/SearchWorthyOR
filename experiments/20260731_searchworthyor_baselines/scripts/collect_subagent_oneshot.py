from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def public_candidate_labels(problem_zh: str) -> list[str]:
    labels = sorted(
        set(
            re.findall(
                r"(?m)^-\s+[^\n：:]*?([A-Z])\s*[：:]",
                problem_zh,
            )
        )
    )
    if not labels:
        raise ValueError("Cannot derive action labels from the public problem.")
    return labels


def semantic_action_to_binary(action: object, labels: list[str]) -> list[int]:
    if isinstance(action, dict):
        return [int(round(float(action.get(label, 0)))) for label in labels]
    if not isinstance(action, list):
        return []
    if all(isinstance(item, (int, float)) for item in action):
        return [int(round(float(item))) for item in action]
    selected = {str(item).strip().upper() for item in action}
    return [int(label in selected) for label in labels]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--baseline", default="gpt56_one_shot")
    parser.add_argument("--condition")
    args = parser.parse_args()

    public_rows = [
        json.loads(line)
        for line in (
            args.dataset_root / "public" / "tasks_zh.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    public_by_id = {row["id"]: row for row in public_rows}
    rows = []
    for result_path in sorted(args.run_root.glob("SWOR*/result.json")):
        raw = json.loads(result_path.read_text(encoding="utf-8-sig"))
        task_id = raw.get("task_id", raw.get("id"))
        if not task_id:
            raise ValueError(f"Missing task id in {result_path}")
        if task_id not in public_by_id:
            raise ValueError(f"Unknown public task: {task_id}")
        labels = public_candidate_labels(
            public_by_id[task_id]["problem_zh"]
        )
        binary_action = semantic_action_to_binary(
            raw.get("projected_action", []), labels
        )
        search_trace_path = result_path.parent / "search_trace.json"
        if search_trace_path.exists():
            loaded_trace = json.loads(
                search_trace_path.read_text(encoding="utf-8-sig")
            )
            if isinstance(loaded_trace, list):
                search_trace = loaded_trace
            elif "query" in loaded_trace and "results" in loaded_trace:
                search_trace = [loaded_trace]
            elif (
                loaded_trace.get("search_trace")
                or loaded_trace.get("events")
                or loaded_trace.get("research_turns")
            ):
                search_trace = loaded_trace.get(
                    "search_trace",
                    loaded_trace.get(
                        "events", loaded_trace.get("research_turns", [])
                    ),
                )
            elif loaded_trace.get("selected_sources"):
                search_trace = [
                    {
                        "query": " | ".join(loaded_trace.get("queries", [])),
                        "results": [
                            {
                                "rank": rank,
                                "url": source.get("url"),
                            }
                            for rank, source in enumerate(
                                loaded_trace["selected_sources"], 1
                            )
                        ],
                    }
                ]
            else:
                search_trace = []
                for query_row in loaded_trace.get("queries", []):
                    raw_results = query_row.get("results")
                    if raw_results is None:
                        raw_results = query_row.get("result_ids", [])
                    normalized_results = []
                    for rank, result in enumerate(raw_results, 1):
                        if isinstance(result, str):
                            normalized_results.append({"rank": rank, "id": result})
                        elif isinstance(result, list):
                            normalized_results.append(
                                {
                                    "rank": rank,
                                    "id": result[0],
                                    "score": result[1] if len(result) > 1 else None,
                                }
                            )
                        else:
                            normalized_results.append(result)
                    search_trace.append(
                        {
                            "query": query_row.get("query", ""),
                            "results": normalized_results,
                        }
                    )
        else:
            search_trace = []
        raw_status = raw.get("status")
        normalized_status = (
            "OPTIMAL"
            if raw_status == 2
            or str(raw_status).upper() == "OPTIMAL"
            or raw.get("solver_status") == 2
            else raw_status
        )
        model_candidates = sorted(result_path.parent.glob("model*.py"))
        rows.append(
            {
                "task_id": task_id,
                "baseline": args.baseline,
                "condition": raw.get("condition", args.condition),
                "requested_model": raw.get(
                    "requested_model", raw.get("model")
                ),
                "actual_model": raw.get("model"),
                "requested_reasoning_effort": raw.get("reasoning_effort"),
                "reasoning_fallback": False,
                "generated_once": raw.get(
                    "generated_once",
                    raw.get("code_attempts") == 1
                    or args.baseline == "gpt56_one_shot",
                ),
                "search_trace": search_trace,
                "selected_evidence_ids": raw.get("selected_evidence_ids", []),
                "selected_urls": raw.get(
                    "selected_urls", raw.get("selected_source_urls", [])
                ),
                "applicability": raw.get("applicability", {}),
                "base_ir": None,
                "typed_patch": {"ops": []},
                "patched_ir": None,
                "gurobi_code": str(
                    model_candidates[0]
                    if model_candidates
                    else result_path.parent / "model.py"
                ),
                "gurobi_result": {
                    "status": normalized_status,
                    "objective": raw.get("objective"),
                    "projected_action": binary_action,
                    "max_constraint_violation": 0.0
                    if normalized_status == "OPTIMAL"
                    else None,
                    "integrality_violation": 0.0
                    if normalized_status == "OPTIMAL"
                    else None,
                },
                "claim_to_model_mapping": [],
                "usage": {},
                "read_scope": raw.get("read_scope", []),
                "epistemic_status": raw.get("epistemic_status"),
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(rows), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
