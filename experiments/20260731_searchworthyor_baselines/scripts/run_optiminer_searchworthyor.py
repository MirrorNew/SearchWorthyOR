from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

from controlled_retrieval import FrozenBM25, read_jsonl
from llm_api import LLMConfig, StrictReasoningClient
from run_prompt_baselines import (
    FINAL_SYSTEM,
    call_and_record,
    extract_json_object,
    final_user_prompt,
    load_solver_backend,
    replay_prediction,
)


SEARCH_RE = re.compile(r"<search>\s*(.*?)\s*</search>", re.DOTALL)
FINAL_RE = re.compile(r"<final>\s*(.*?)\s*</final>", re.DOTALL)


OPTIMINER_CONTROLLER = """You are the training-free OptiMiner controller.
The external rule is allowed to change the mathematical model. Your job is to
detect which knowledge is missing, search by natural entity/date/jurisdiction/
business semantics, adjudicate authority and applicability, then bind claims
to variables, domains, constraints, objective terms, equations, and Gurobi
code.

At each research turn return exactly one action:
<search>natural-language query</search>
or, when evidence is sufficient:
<final>the complete JSON submission</final>

Do not query document IDs. Do not stop after merely finding a semantically
similar document. Check authority, effective interval, jurisdiction, subject,
and exceptions. A search call is useful only if the final model cites and uses
its evidence."""


def compact_results(results: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        f"[rank={rank}; id={row['id']}; score={row['score']:.6f}]\n{row['content']}"
        for rank, row in enumerate(results, 1)
    )


def run_agent(
    client: StrictReasoningClient,
    task: dict[str, Any],
    condition: str,
    index: FrozenBM25,
    oracle_document: dict[str, Any] | None,
    max_research_turns: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], str]:
    calls: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []

    if condition == "no_search":
        prompt = final_user_prompt(task, [], "")
        raw = call_and_record(
            client,
            [
                {"role": "system", "content": FINAL_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            calls,
            "optiminer_no_search_final",
        )
        return extract_json_object(raw), calls, trace, raw

    if condition == "oracle_evidence":
        if oracle_document is None:
            raise RuntimeError("Oracle evidence missing.")
        prompt = final_user_prompt(task, [oracle_document], "")
        raw = call_and_record(
            client,
            [
                {"role": "system", "content": FINAL_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            calls,
            "optiminer_oracle_final",
        )
        trace.append(
            {
                "query": "<oracle-evidence>",
                "results": [{"rank": 1, "id": oracle_document["id"], "score": 1.0}],
            }
        )
        return extract_json_object(raw), calls, trace, raw

    messages = [
        {"role": "system", "content": OPTIMINER_CONTROLLER},
        {
            "role": "user",
            "content": (
                task["problem_zh"]
                + "\n\n先判断缺失知识并搜索。完成检索后，final JSON 必须遵循以下最终合同：\n"
                + final_user_prompt(task, [], "")
            ),
        },
    ]
    searched = False
    last_raw = ""
    for turn in range(max_research_turns + 1):
        last_raw = call_and_record(
            client, messages, calls, f"optiminer_turn_{turn + 1}"
        )
        search_match = SEARCH_RE.search(last_raw)
        final_match = FINAL_RE.search(last_raw)
        if search_match:
            query = search_match.group(1).strip()
            if not query or re.fullmatch(r"(?:DOC|EVID)[-_A-Z0-9]+", query, re.I):
                raise ValueError("Exact-ID or empty search query is forbidden.")
            results = index.search(query, 5)
            trace.append(
                {
                    "query": query,
                    "results": [
                        {"rank": rank, "id": row["id"], "score": row["score"]}
                        for rank, row in enumerate(results, 1)
                    ],
                }
            )
            searched = True
            messages.extend(
                [
                    {"role": "assistant", "content": last_raw},
                    {
                        "role": "user",
                        "content": "<result>\n" + compact_results(results) + "\n</result>",
                    },
                ]
            )
            continue
        if final_match:
            if not searched:
                raise RuntimeError(
                    "Corpus-search condition requires at least one successful search."
                )
            return extract_json_object(final_match.group(1)), calls, trace, last_raw
        if searched:
            try:
                prediction = extract_json_object(last_raw)
            except ValueError:
                messages.extend(
                    [
                        {"role": "assistant", "content": last_raw},
                        {
                            "role": "user",
                            "content": "只返回 <search>...</search> 或 <final>{...}</final>。",
                        },
                    ]
                )
                continue
            return prediction, calls, trace, last_raw
        raise RuntimeError("OptiMiner returned neither search nor final action.")
    raise RuntimeError("OptiMiner exceeded max_research_turns without a final answer.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--condition",
        required=True,
        choices=["no_search", "corpus_search", "oracle_evidence"],
    )
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--model", default="gpt-5.6")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--max-research-turns", type=int, default=3)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    tasks = read_jsonl(args.dataset_root / "public" / "tasks_zh.jsonl")
    if args.ids:
        wanted = set(args.ids)
        tasks = [task for task in tasks if task["id"] in wanted]
    if args.limit is not None:
        tasks = tasks[: args.limit]
    evidence_rows = read_jsonl(
        args.dataset_root / "private" / "evidence_corpus.jsonl"
    )
    evidence_by_id = {row["id"]: row for row in evidence_rows}
    index = FrozenBM25(evidence_rows)
    if args.condition == "oracle_evidence":
        gold_rows = read_jsonl(args.dataset_root / "private" / "gold.jsonl")
        gold_by_id = {row["id"]: row for row in gold_rows}
    else:
        gold_by_id = {}
    solver_backend = load_solver_backend(args.dataset_root)
    client = StrictReasoningClient(
        LLMConfig.from_environment(args.model, args.reasoning_effort)
    )

    run_dir = args.output_dir / "optiminer_training_free" / args.condition
    run_dir.mkdir(parents=True, exist_ok=True)
    submission_path = run_dir / "submissions.jsonl"
    if submission_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"{submission_path} already exists; pass --overwrite for a fresh run."
        )
    if args.overwrite:
        submission_path.write_text("", encoding="utf-8")
    for task in tasks:
        task_dir = run_dir / task["id"]
        task_dir.mkdir(parents=True, exist_ok=True)
        oracle_document = None
        if args.condition == "oracle_evidence":
            evidence_id = gold_by_id[task["id"]]["applicability"][
                "selected_evidence_id"
            ]
            oracle_document = evidence_by_id[evidence_id]
        started = time.perf_counter()
        try:
            prediction, calls, trace, raw = run_agent(
                client,
                task,
                args.condition,
                index,
                oracle_document,
                args.max_research_turns,
            )
            gurobi_result = replay_prediction(prediction, solver_backend)
            actual_models = sorted(
                {str(call["actual_model"]) for call in calls if call["actual_model"]}
            )
            submission = {
                "task_id": task["id"],
                "baseline": "optiminer_training_free",
                "condition": args.condition,
                "requested_model": args.model,
                "actual_model": actual_models,
                "requested_reasoning_effort": args.reasoning_effort,
                "reasoning_fallback": any(
                    call["reasoning_fallback"] for call in calls
                ),
                "generated_once": False,
                "search_trace": trace,
                "selected_evidence_ids": prediction.get(
                    "selected_evidence_ids", []
                ),
                "applicability": prediction.get("applicability", {}),
                "base_ir": prediction.get("base_ir"),
                "typed_patch": prediction.get("typed_patch", {"ops": []}),
                "patched_ir": prediction.get("patched_ir"),
                "gurobi_code": prediction.get("gurobi_code", ""),
                "gurobi_result": gurobi_result,
                "claim_to_model_mapping": prediction.get(
                    "claim_to_model_mapping", []
                ),
                "usage": {
                    "calls": calls,
                    "call_count": len(calls),
                    "wall_seconds": time.perf_counter() - started,
                },
            }
            status = "ok"
        except Exception as exc:  # noqa: BLE001 - experiment artifact
            submission = {
                "task_id": task["id"],
                "baseline": "optiminer_training_free",
                "condition": args.condition,
                "requested_model": args.model,
                "actual_model": [],
                "requested_reasoning_effort": args.reasoning_effort,
                "reasoning_fallback": False,
                "generated_once": False,
                "search_trace": [],
                "selected_evidence_ids": [],
                "applicability": {},
                "base_ir": None,
                "typed_patch": {"ops": []},
                "patched_ir": None,
                "gurobi_code": "",
                "gurobi_result": {
                    "status": "ERROR",
                    "error": f"{type(exc).__name__}: {exc}",
                },
                "claim_to_model_mapping": [],
                "usage": {"wall_seconds": time.perf_counter() - started},
            }
            raw = ""
            status = "error"
        (task_dir / "submission.json").write_text(
            json.dumps(submission, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (task_dir / "raw_response.txt").write_text(raw, encoding="utf-8")
        with submission_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(submission, ensure_ascii=False) + "\n")
        print(json.dumps({"task_id": task["id"], "status": status}, ensure_ascii=False))
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
