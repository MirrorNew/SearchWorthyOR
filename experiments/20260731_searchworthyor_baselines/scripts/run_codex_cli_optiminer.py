from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from controlled_retrieval import FrozenBM25, read_jsonl
from run_codex_cli_one_shot import (
    load_solver_backend,
    run_one,
    safe_progress,
)
from run_codex_cli_prompt_adapter import call_json_stage


def compact_results(results: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        "\n".join(
            [
                f"rank={rank}; id={row['id']}; score={row['score']:.6f}",
                row["content"],
            ]
        )
        for rank, row in enumerate(results, 1)
    )


def controller_prompt(
    task: dict[str, Any],
    history: list[str],
    turn: int,
    max_turns: int,
) -> str:
    return f"""你是 training-free OptiMiner 的搜索控制器。你不直接写最终模型，只判断是否仍缺少
会改变 OR 变量、变量域、约束、作用域、条件逻辑或目标结构的外部规则。

任务 ID：{task["id"]}
决策时间：{task["decision_time"]}
实体：{task["entity"]}
辖区：{task["jurisdiction"]}

公开任务：
{task["problem_zh"]}

已有搜索历史：
{chr(10).join(history) if history else "（无）"}

当前研究轮：{turn}/{max_turns}

若仍缺证据，action=`search`，query 必须只使用自然实体、日期、辖区和业务语义，
不得包含任务 ID、DOC ID 或精确文档标识。若已有证据足以唯一裁决权威性、时点、辖区、
主体与例外，action=`final`，query 设为空字符串。reason 说明未解决槽位或停止依据。
不得调用工具；只返回 schema JSON。"""


def run_search_controller(
    task: dict[str, Any],
    index: FrozenBM25,
    task_dir: Path,
    sterile_dir: Path,
    codex_executable: str,
    action_schema: Path,
    model: str,
    reasoning_effort: str,
    max_research_turns: int,
    reuse_existing_response: bool = False,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    str,
    list[dict[str, Any]],
]:
    history: list[str] = []
    trace: list[dict[str, Any]] = []
    documents: dict[str, dict[str, Any]] = {}
    records = []
    searched = False
    for turn in range(1, max_research_turns + 2):
        response, record = call_json_stage(
            controller_prompt(
                task, history, turn, max_research_turns
            ),
            f"controller_turn_{turn}",
            task_dir,
            sterile_dir / f"controller_turn_{turn}",
            codex_executable,
            action_schema,
            model,
            reasoning_effort,
            reuse_existing_response,
        )
        records.append(record)
        action = response["action"]
        query = response["query"].strip()
        reason = response["reason"].strip()
        if action == "final":
            if not searched:
                raise RuntimeError(
                    "Corpus-search controller stopped before any search."
                )
            history.append(f"停止：{reason}")
            return list(documents.values()), trace, "\n".join(history), records
        if turn > max_research_turns:
            raise RuntimeError(
                "OptiMiner exceeded max research turns without final."
            )
        if (
            not query
            or re.search(r"\b(?:SWOR|DOC)[-_A-Z0-9]*\b", query, re.I)
        ):
            raise ValueError(
                f"Forbidden empty or identifier query: {query!r}"
            )
        results = index.search(query, 5)
        searched = True
        trace.append(
            {
                "query": query,
                "reason": reason,
                "results": [
                    {
                        "rank": rank,
                        "id": row["id"],
                        "score": row["score"],
                    }
                    for rank, row in enumerate(results, 1)
                ],
            }
        )
        for row in results:
            documents.setdefault(row["id"], row)
        history.append(
            "\n".join(
                [
                    f"第 {turn} 轮 query：{query}",
                    f"搜索理由：{reason}",
                    "<result>",
                    compact_results(results),
                    "</result>",
                ]
            )
        )
    raise RuntimeError("Unreachable controller state.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--condition",
        required=True,
        choices=["no_search", "corpus_search"],
    )
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--sterile-root", required=True, type=Path)
    parser.add_argument("--codex", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument(
        "--final-schema",
        default=Path("configs/cli_one_shot_output_schema.json"),
        type=Path,
    )
    parser.add_argument(
        "--action-schema",
        default=Path("configs/cli_search_action_schema.json"),
        type=Path,
    )
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--max-research-turns", type=int, default=3)
    parser.add_argument(
        "--source-reproduction",
        default=(
            Path(__file__).resolve().parents[3]
            / "run_optminer_training_free.py"
        ),
        type=Path,
    )
    parser.add_argument("--task-id", action="append")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    dataset_root = args.dataset_root.resolve()
    tasks = read_jsonl(dataset_root / "public" / "tasks_zh.jsonl")
    if args.task_id:
        wanted = set(args.task_id)
        tasks = [task for task in tasks if task["id"] in wanted]
    if args.limit is not None:
        tasks = tasks[: args.limit]
    if args.num_shards < 1:
        raise ValueError("--num-shards must be positive.")
    if not 0 <= args.shard_index < args.num_shards:
        raise ValueError("--shard-index must be in [0, num_shards).")
    tasks = [
        task
        for index, task in enumerate(tasks)
        if index % args.num_shards == args.shard_index
    ]
    evidence_rows = read_jsonl(
        dataset_root / "private" / "evidence_corpus.jsonl"
    )
    evidence_index = FrozenBM25(evidence_rows)
    solver_backend = load_solver_backend(dataset_root)
    output_root = args.output_root.resolve()
    sterile_root = args.sterile_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    sterile_root.mkdir(parents=True, exist_ok=True)
    codex_path = Path(args.codex).resolve()
    source_reproduction = args.source_reproduction.resolve()
    runner_files = [
        Path(__file__).resolve(),
        Path(__file__).resolve().with_name("controlled_retrieval.py"),
        Path(__file__).resolve().with_name(
            "run_codex_cli_prompt_adapter.py"
        ),
        Path(__file__).resolve().with_name("run_codex_cli_one_shot.py"),
    ]
    (output_root / "run_manifest.json").write_text(
        json.dumps(
            {
                "baseline": "optiminer_training_free_compat_cli",
                "condition": args.condition,
                "codex_path": str(codex_path),
                "codex_sha256": hashlib.sha256(
                    codex_path.read_bytes()
                ).hexdigest(),
                "model": args.model,
                "reasoning_effort": args.reasoning_effort,
                "max_research_turns": args.max_research_turns,
                "controller_cli_timeout_seconds": 180,
                "final_cli_timeout_seconds": 180,
                "training_free": True,
                "compatibility_adapter_not_unmodified_reproduction": True,
                "runner_files": [
                    {
                        "path": str(path),
                        "sha256": hashlib.sha256(
                            path.read_bytes()
                        ).hexdigest(),
                    }
                    for path in runner_files
                ],
                "source_reproduction_path": str(source_reproduction),
                "source_reproduction_sha256": hashlib.sha256(
                    source_reproduction.read_bytes()
                ).hexdigest(),
                "intentional_contract_change": (
                    "SearchWorthyOR external evidence may add business "
                    "constraints; the source reproduction allows external "
                    "documents only as modeling or solver hints."
                ),
                "retries": 0,
                "num_shards": args.num_shards,
                "shard_index": args.shard_index,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    submissions = []
    failures = []
    for index, task in enumerate(tasks, 1):
        task_dir = output_root / task["id"]
        existing = task_dir / "submission.json"
        existing_failure = task_dir / "failure.json"
        if args.resume and existing.exists():
            submissions.append(
                json.loads(existing.read_text(encoding="utf-8-sig"))
            )
            safe_progress(
                {
                    "index": index,
                    "total": len(tasks),
                    "task_id": task["id"],
                    "status": "RESUMED",
                }
            )
            continue
        if (
            args.resume
            and existing_failure.exists()
            and (task_dir / "model_response.json").exists()
        ):
            failure = json.loads(
                existing_failure.read_text(encoding="utf-8-sig")
            )
            failures.append(failure)
            safe_progress(
                {
                    "index": index,
                    "total": len(tasks),
                    "task_id": task["id"],
                    "status": "SKIPPED_EXISTING_MODEL_FAILURE",
                }
            )
            continue
        try:
            if args.condition == "corpus_search":
                (
                    documents,
                    search_trace,
                    scratchpad,
                    controller_records,
                ) = run_search_controller(
                    task,
                    evidence_index,
                    task_dir,
                    sterile_root / task["id"],
                    args.codex,
                    args.action_schema,
                    args.model,
                    args.reasoning_effort,
                    args.max_research_turns,
                    args.resume,
                )
            else:
                documents = []
                search_trace = []
                scratchpad = ""
                controller_records = []
            submission = run_one(
                task=task,
                condition=args.condition,
                documents=documents,
                search_trace=search_trace,
                task_dir=task_dir,
                sterile_dir=sterile_root / task["id"] / "final",
                codex_executable=args.codex,
                python_executable=args.python,
                output_schema=args.final_schema,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                solver_backend=solver_backend,
                baseline="optiminer_training_free_compat_cli",
                scratchpad=scratchpad,
                reuse_existing_response=args.resume,
            )
            submission["usage"]["controller_calls"] = controller_records
            submission["usage"]["controller_call_count"] = len(
                controller_records
            )
            submission["usage"]["search_call_count"] = len(search_trace)
            (task_dir / "submission.json").write_text(
                json.dumps(
                    submission, ensure_ascii=False, indent=2
                )
                + "\n",
                encoding="utf-8",
            )
            if args.resume and existing_failure.exists():
                (task_dir / "resume_resolution.json").write_text(
                    json.dumps(
                        {
                            "status": (
                                "recovered_from_existing_stage_artifacts"
                            ),
                            "stale_failure_file_preserved": "failure.json",
                            "reused_controller_stages": [
                                record["stage"]
                                for record in controller_records
                                if record.get(
                                    "reused_existing_response"
                                )
                            ],
                            "reused_final_model_response": submission[
                                "usage"
                            ].get(
                                "reused_existing_model_response",
                                False,
                            ),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            submissions.append(submission)
            safe_progress(
                {
                    "index": index,
                    "total": len(tasks),
                    "task_id": task["id"],
                    "status": submission["gurobi_result"].get("status"),
                }
            )
        except Exception as exc:  # noqa: BLE001 - experiment failure
            failure = {
                "task_id": task["id"],
                "type": type(exc).__name__,
                "message": str(exc),
            }
            failures.append(failure)
            task_dir.mkdir(parents=True, exist_ok=True)
            (task_dir / "failure.json").write_text(
                json.dumps(failure, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            safe_progress(
                {
                    "index": index,
                    "total": len(tasks),
                    **failure,
                }
            )
    (output_root / "submissions.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False) + "\n"
            for row in submissions
        ),
        encoding="utf-8",
    )
    (output_root / "failures.json").write_text(
        json.dumps(failures, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    safe_progress(
        {
            "requested": len(tasks),
            "completed": len(submissions),
            "failed": len(failures),
        }
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
