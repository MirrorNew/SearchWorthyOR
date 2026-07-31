from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from controlled_retrieval import FrozenBM25, read_jsonl
from verify_pilot_artifacts import parse_last_json_object, static_code_check


ALLOWED_ITEM_TYPES = {"agent_message", "reasoning"}
ALLOWED_EVENT_TYPES = {
    "thread.started",
    "turn.started",
    "item.started",
    "item.updated",
    "item.completed",
    "turn.completed",
}
KNOWN_BENIGN_ERROR_PREFIX = "Skill descriptions were shortened"


def safe_progress(payload: dict[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False), flush=True)
    except OSError:
        return


def load_solver_backend(dataset_root: Path):
    path = dataset_root / "scripts" / "solver_backend.py"
    spec = importlib.util.spec_from_file_location(
        "searchworthyor_solver_backend", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import solver backend from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def format_evidence(documents: list[dict[str, Any]]) -> str:
    if not documents:
        return "（没有提供外部证据。）"
    blocks = []
    for document in documents:
        public_metadata = {
            key: value
            for key, value in document.items()
            if key not in {"content"}
        }
        blocks.append(
            "\n".join(
                [
                    f"证据候选 {document['id']}",
                    json.dumps(
                        public_metadata,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    document["content"],
                ]
            )
        )
    return "\n\n---\n\n".join(blocks)


def build_prompt(
    task: dict[str, Any],
    condition: str,
    documents: list[dict[str, Any]],
    scratchpad: str = "",
) -> str:
    if condition == "no_search":
        evidence_instruction = (
            "本条件禁止外部搜索且没有提供证据。不得用模型记忆猜测外部政策；"
            "base_ir 与 patched_ir 必须相同，selected_evidence_ids 和 typed patch ops 必须为空。"
        )
        tool_instruction = (
            "不得调用任何工具、命令、文件读取、网络搜索或额外 Agent。"
        )
    elif condition == "corpus_search":
        evidence_instruction = (
            "候选证据是冻结检索接口返回的 top-k。请依据权威性、决策时点、辖区、主体和例外"
            "选择唯一适用证据；不得因为排序靠前就采用。只有适用证据才能改变模型。"
        )
        tool_instruction = (
            "不得调用任何工具、命令、文件读取、网络搜索或额外 Agent。"
        )
    elif condition == "live_web":
        evidence_instruction = (
            "请使用内置网页搜索定位题面要求的官方一手来源，并核验决策时点、辖区、主体、"
            "版本和例外。selected_evidence_ids 中直接填写采用的官方 URL；若无法取得足以"
            "改变模型的适用证据，必须保持 patched IR 与 base IR 相同。"
        )
        tool_instruction = (
            "仅可调用内置网页搜索；不得调用 shell、命令、文件读取、插件或额外 Agent。"
        )
    else:
        raise ValueError(f"Unsupported condition: {condition}")
    return f"""你是运筹优化建模专家。完成一次单轮建模。{tool_instruction}
只根据公开任务以及本轮网页搜索或提示内证据作答。模型必须是单目标线性 0-1 MILP。

任务 ID：{task["id"]}
决策时间：{task["decision_time"]}
实体：{task["entity"]}
辖区：{task["jurisdiction"]}

公开任务：
{task["problem_zh"]}

证据条件：{condition}
{evidence_instruction}

可用证据：
{format_evidence(documents)}

此前提示阶段产生的工作记录（仅供核对，不得覆盖题面或证据）：
{scratchpad or "（无）"}

输出契约：

1. `base_ir_json`、`patched_ir_json`、`typed_patch_json` 和
   `claim_to_model_mapping_json` 都是“JSON 文本字符串”，字符串内部必须能再次被
   `json.loads` 解析，不能使用 Markdown。
2. 两个 IR 必须使用以下 canonical 结构：
   - `model_id`, `world`, `sense` (`max` 或 `min`), `single_objective=true`
   - `variables`: 按题面候选顺序命名为 `x_0`, `x_1`, ...；每项含
     `name`, `vartype="B"`, `lb=0`, `ub=1`, `semantic_name`
   - `objective`: `constant` 与 `terms`；terms 是变量名到数值系数的 JSON object
   - `constraints`: 每项含唯一 `name`, `sense` (`<=`, `>=`, `==`),
     数值 `rhs`, 以及变量名到数值系数的 `terms` object
   - `action_projection`: 按题面候选顺序列出 `x_0`, `x_1`, ...
3. `base_ir_json` 只编码题面冻结的基础模型；`patched_ir_json` 是采用适用证据后的模型。
   不得删除或改写与证据无关的基础目标、变量和约束。
4. `typed_patch_json` 结构为 `{{"ops":[...]}}`。每个 op 必须含：
   `op`, `slot_type`, `evidence_id`, `before_expression`, `after_expression`。
5. `claim_to_model_mapping_json` 是数组；每项必须含：
   `evidence_id`, `claim`, `model_slot`, `equation`, `code_region`。
6. `gurobi_code` 必须是完整、自包含的 Python 源码，只能导入
   `gurobipy`, `json`, `math`；直接编码 patched IR，不读文件、不联网、不调用输入，
   不得把 Gold 行动固定进变量。代码设置单目标、求解，并打印一个 JSON object，至少包含
   `status`, `objective`, `projected_action`, `max_constraint_violation`,
   `integrality_violation`。`projected_action` 必须是与 action_projection 同序的 0/1 数组。
7. 如果证据不足，明确说明，保持 patched IR 与 base IR 相同，不得虚构规则。

只返回 output schema 要求的 JSON object。"""


def prepare_context(
    task: dict[str, Any],
    condition: str,
    evidence_index: FrozenBM25,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if condition in {"no_search", "live_web"}:
        return [], []
    if condition != "corpus_search":
        raise ValueError(f"Unsupported condition: {condition}")
    query = " ".join(
        [
            task["entity"],
            task["jurisdiction"],
            task["decision_time"],
        ]
    )
    documents = evidence_index.search(query, 5)
    trace = [
        {
            "query": query,
            "results": [
                {
                    "rank": rank,
                    "id": document["id"],
                    "score": document["score"],
                }
                for rank, document in enumerate(documents, 1)
            ],
        }
    ]
    return documents, trace


def parse_events(
    text: str,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    events = []
    usage: dict[str, Any] = {}
    non_json_lines = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            non_json_lines.append(line)
            continue
        events.append(event)
        if event.get("type") == "turn.completed":
            usage = event.get("usage", {})
    return events, usage, non_json_lines


def audit_events(
    events: list[dict[str, Any]],
    non_json_lines: list[str],
    allow_web_search: bool = False,
) -> dict[str, Any]:
    violations = []
    warnings = []
    allowed_item_types = set(ALLOWED_ITEM_TYPES)
    if allow_web_search:
        allowed_item_types.add("web_search")
    if non_json_lines:
        violations.append(
            {
                "type": "non_json_stdout",
                "count": len(non_json_lines),
            }
        )
    for event in events:
        event_type = event.get("type")
        if event_type not in ALLOWED_EVENT_TYPES:
            violations.append(
                {"type": "unexpected_event", "event_type": event_type}
            )
            continue
        if event_type not in {
            "item.started",
            "item.updated",
            "item.completed",
        }:
            continue
        item = event.get("item", {})
        item_type = item.get("type")
        if item_type == "error":
            message = str(item.get("message", ""))
            if message.startswith(KNOWN_BENIGN_ERROR_PREFIX):
                warnings.append(message)
                continue
        if item_type not in allowed_item_types:
            violations.append(
                {
                    "type": "forbidden_item",
                    "event_type": event_type,
                    "item_type": item_type,
                    "item_id": item.get("id"),
                }
            )
    counts = {
        event_type: sum(
            event.get("type") == event_type for event in events
        )
        for event_type in (
            "thread.started",
            "turn.started",
            "turn.completed",
        )
    }
    for event_type, count in counts.items():
        if count != 1:
            violations.append(
                {
                    "type": "event_count",
                    "event_type": event_type,
                    "expected": 1,
                    "actual": count,
                }
            )
    completed_messages = [
        event
        for event in events
        if event.get("type") == "item.completed"
        and event.get("item", {}).get("type") == "agent_message"
    ]
    completed_items = [
        event
        for event in events
        if event.get("type") == "item.completed"
        and event.get("item", {}).get("type") != "error"
    ]
    completed_web_searches = [
        event
        for event in completed_items
        if event.get("item", {}).get("type") == "web_search"
    ]
    if allow_web_search:
        if not completed_messages:
            violations.append(
                {
                    "type": "final_message_count",
                    "expected": "at_least_one",
                    "actual": 0,
                }
            )
        if not completed_web_searches:
            violations.append(
                {
                    "type": "web_search_count",
                    "expected": "at_least_one",
                    "actual": 0,
                }
            )
        if (
            completed_items
            and completed_items[-1].get("item", {}).get("type")
            != "agent_message"
        ):
            violations.append(
                {
                    "type": "final_completed_item",
                    "expected": "agent_message",
                    "actual": completed_items[-1]
                    .get("item", {})
                    .get("type"),
                }
            )
    elif len(completed_messages) != 1:
        violations.append(
            {
                "type": "final_message_count",
                "expected": 1,
                "actual": len(completed_messages),
            }
        )
    return {
        "passed": not violations,
        "violations": violations,
        "warnings": warnings,
        "allow_web_search": allow_web_search,
        "counts": counts,
        "completed_agent_messages": len(completed_messages),
        "completed_web_searches": len(completed_web_searches),
    }


def extract_web_search_trace(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    trace = []
    for event in events:
        if event.get("type") != "item.completed":
            continue
        item = event.get("item", {})
        if item.get("type") != "web_search":
            continue
        query = item.get("query")
        if not query and isinstance(item.get("action"), dict):
            query = item["action"].get("query")
        urls = []

        def collect_urls(value: Any) -> None:
            if isinstance(value, str) and value.startswith(
                ("http://", "https://")
            ):
                if value not in urls:
                    urls.append(value)
            elif isinstance(value, dict):
                for nested in value.values():
                    collect_urls(nested)
            elif isinstance(value, list):
                for nested in value:
                    collect_urls(nested)

        collect_urls(item)
        trace.append(
            {
                "query": query or "",
                "results": [
                    {"rank": rank, "url": url}
                    for rank, url in enumerate(urls, 1)
                ],
            }
        )
    return trace


def execute_generated_code(
    code_path: Path,
    python_executable: str,
) -> dict[str, Any]:
    check = static_code_check(code_path)
    if not check["passed"]:
        return {
            "passed": False,
            "static_check": check,
            "reason": "static_code_check_failed",
        }
    completed = subprocess.run(
        [python_executable, str(code_path.resolve())],
        cwd=code_path.parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    stdout_path = code_path.parent / "model_execution.stdout.txt"
    stderr_path = code_path.parent / "model_execution.stderr.txt"
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    try:
        result = parse_last_json_object(completed.stdout)
    except ValueError:
        result = {}
    return {
        "passed": (
            completed.returncode == 0
            and not completed.stderr.strip()
            and bool(result)
        ),
        "returncode": completed.returncode,
        "stderr_empty": not completed.stderr.strip(),
        "static_check": check,
        "result": result,
    }


def normalize_response(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": raw["task_id"],
        "selected_evidence_ids": raw["selected_evidence_ids"],
        "applicability": raw["applicability"],
        "base_ir": json.loads(raw["base_ir_json"]),
        "typed_patch": json.loads(raw["typed_patch_json"]),
        "patched_ir": json.loads(raw["patched_ir_json"]),
        "gurobi_code": raw["gurobi_code"],
        "claim_to_model_mapping": json.loads(
            raw["claim_to_model_mapping_json"]
        ),
    }


def run_one(
    task: dict[str, Any],
    condition: str,
    documents: list[dict[str, Any]],
    search_trace: list[dict[str, Any]],
    task_dir: Path,
    sterile_dir: Path,
    codex_executable: str,
    python_executable: str,
    output_schema: Path,
    model: str,
    reasoning_effort: str,
    solver_backend: Any,
    baseline: str = "gpt56_sol_codex_cli_one_shot",
    scratchpad: str = "",
    reuse_existing_response: bool = False,
    cli_timeout_seconds: int = 180,
) -> dict[str, Any]:
    task_dir.mkdir(parents=True, exist_ok=True)
    sterile_dir.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(task, condition, documents, scratchpad)
    (task_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    final_path = task_dir / "model_response.json"
    command = [codex_executable]
    if condition == "live_web":
        command.append("--search")
    command.extend([
        "exec",
        "-m",
        model,
        "-c",
        f'model_reasoning_effort="{reasoning_effort}"',
        "-c",
        "features.shell_tool=false",
        "-c",
        f'web_search="{"live" if condition == "live_web" else "disabled"}"',
        "-c",
        "agents.enabled=false",
        "-c",
        "features.remote_plugin=false",
        "-c",
        "features.shell_snapshot=false",
        "--json",
        "--output-schema",
        str(output_schema.resolve()),
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "-s",
        "read-only",
        "-C",
        str(sterile_dir.resolve()),
        "-o",
        str(final_path.resolve()),
        "-",
    ])
    events_path = task_dir / "codex_events.jsonl"
    stderr_path = task_dir / "codex.stderr.txt"
    can_reuse = (
        reuse_existing_response
        and final_path.exists()
        and events_path.exists()
        and stderr_path.exists()
    )
    if can_reuse:
        stdout_text = events_path.read_text(encoding="utf-8")
        stderr_text = stderr_path.read_text(encoding="utf-8")
        returncode = 0
        elapsed = 0.0
    else:
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=cli_timeout_seconds,
            check=False,
        )
        elapsed = time.perf_counter() - started
        stdout_text = completed.stdout
        stderr_text = completed.stderr
        returncode = completed.returncode
        events_path.write_text(stdout_text, encoding="utf-8")
        stderr_path.write_text(stderr_text, encoding="utf-8")
    events, usage, non_json_lines = parse_events(stdout_text)
    event_audit = audit_events(
        events,
        non_json_lines,
        allow_web_search=condition == "live_web",
    )
    if returncode != 0:
        raise RuntimeError(
            f"Codex CLI failed with exit code {returncode}"
        )
    if not event_audit["passed"]:
        raise RuntimeError(
            "Single-turn event contract violated: "
            f"{event_audit['violations']}"
        )
    raw = json.loads(final_path.read_text(encoding="utf-8-sig"))
    response = normalize_response(raw)
    if condition == "live_web":
        search_trace = extract_web_search_trace(events)
    if response["task_id"] != task["id"]:
        raise ValueError(
            f"Task id mismatch: {response['task_id']} != {task['id']}"
        )

    code_path = task_dir / "model.py"
    code_path.write_text(response["gurobi_code"], encoding="utf-8")
    code_execution = execute_generated_code(
        code_path, python_executable
    )
    trusted_gurobi = solver_backend.solve_gurobi(
        response["patched_ir"]
    )
    trusted_exact = solver_backend.enumerate_optimal_actions(
        response["patched_ir"]
    )
    submission = {
        "task_id": task["id"],
        "baseline": baseline,
        "condition": condition,
        "requested_model": model,
        "actual_model": model,
        "requested_reasoning_effort": reasoning_effort,
        "reasoning_fallback": False,
        "reasoning_metadata_verified": False,
        "generated_once": True,
        "search_trace": search_trace,
        "selected_evidence_ids": response["selected_evidence_ids"],
        "selected_urls": [
            reference
            for reference in response["selected_evidence_ids"]
            if reference.startswith(("http://", "https://"))
        ],
        "applicability": response["applicability"],
        "base_ir": response["base_ir"],
        "typed_patch": response["typed_patch"],
        "patched_ir": response["patched_ir"],
        "gurobi_code": str(code_path.resolve()),
        "gurobi_result": trusted_gurobi,
        "claim_to_model_mapping": response[
            "claim_to_model_mapping"
        ],
        "usage": {
            **usage,
            "wall_seconds": elapsed,
            "cli_timeout_seconds": cli_timeout_seconds,
            "codex_cli_returncode": returncode,
            "reused_existing_model_response": can_reuse,
            "event_audit": event_audit,
            "model_code_execution": code_execution,
            "trusted_exact_enumeration": trusted_exact,
        },
        "read_scope": {
            "model_prompt": [
                "public task text",
                "retrieved evidence shown inline"
                if documents
                else (
                    "native live web search"
                    if condition == "live_web"
                    else "no external evidence"
                ),
            ],
            "cli_event_audit": event_audit,
            "gold_available_to_model": False,
        },
    }
    (task_dir / "submission.json").write_text(
        json.dumps(submission, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return submission


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument(
        "--condition",
        required=True,
        choices=["no_search", "corpus_search", "live_web"],
    )
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--codex", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--sterile-root", required=True, type=Path)
    parser.add_argument(
        "--output-schema",
        default=Path("configs/cli_one_shot_output_schema.json"),
        type=Path,
    )
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--task-id", action="append")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--cli-timeout", type=int)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    cli_timeout = (
        args.cli_timeout
        if args.cli_timeout is not None
        else (420 if args.condition == "live_web" else 180)
    )
    if cli_timeout <= 0:
        raise ValueError("--cli-timeout must be positive.")

    dataset_root = args.dataset_root.resolve()
    tasks = read_jsonl(dataset_root / "public" / "tasks_zh.jsonl")
    if args.task_id:
        selected = set(args.task_id)
        tasks = [task for task in tasks if task["id"] in selected]
        missing = selected - {task["id"] for task in tasks}
        if missing:
            raise ValueError(f"Unknown task ids: {sorted(missing)}")
    if args.condition == "live_web":
        tasks = [
            task
            for task in tasks
            if "HTTPS" in task["problem_zh"]
        ]
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
    output_root.mkdir(parents=True, exist_ok=True)
    sterile_root = args.sterile_root.resolve()
    sterile_root.mkdir(parents=True, exist_ok=True)
    codex_path = Path(args.codex).resolve()
    codex_sha256 = hashlib.sha256(codex_path.read_bytes()).hexdigest()
    version_run = subprocess.run(
        [str(codex_path), "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    if version_run.returncode != 0:
        raise RuntimeError("Codex CLI version preflight failed.")
    run_manifest = {
        "codex_path": str(codex_path),
        "codex_sha256": codex_sha256,
        "codex_version": version_run.stdout.strip(),
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "condition": args.condition,
        "single_process_per_task": True,
        "cli_timeout_seconds": cli_timeout,
        "retries": 0,
        "tool_policy": {
            "features.shell_tool": False,
            "web_search": (
                "live"
                if args.condition == "live_web"
                else "disabled"
            ),
            "agents.enabled": False,
            "event_allowlist_enforced": True,
        },
        "sterile_root": str(sterile_root),
    }
    (output_root / "run_manifest.json").write_text(
        json.dumps(run_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    submissions = []
    failures = []
    for index, task in enumerate(tasks, 1):
        documents, search_trace = prepare_context(
            task, args.condition, evidence_index
        )
        task_dir = output_root / task["id"]
        existing_submission = task_dir / "submission.json"
        if args.resume and existing_submission.exists():
            submissions.append(
                json.loads(
                    existing_submission.read_text(encoding="utf-8-sig")
                )
            )
            stale_failure = task_dir / "failure.json"
            if stale_failure.exists():
                (task_dir / "resume_resolution.json").write_text(
                    json.dumps(
                        {
                            "status": "submission_precedes_transport_failure",
                            "submission_retained": True,
                            "stale_failure_file_ignored": "failure.json",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
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
        try:
            submission = run_one(
                task=task,
                condition=args.condition,
                documents=documents,
                search_trace=search_trace,
                task_dir=task_dir,
                sterile_dir=sterile_root / task["id"],
                codex_executable=args.codex,
                python_executable=args.python,
                output_schema=args.output_schema,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                solver_backend=solver_backend,
                reuse_existing_response=args.resume,
                cli_timeout_seconds=cli_timeout,
            )
            submissions.append(submission)
        except Exception as exc:  # noqa: BLE001 - experiment failure artifact
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
            continue
        safe_progress(
            {
                "index": index,
                "total": len(tasks),
                "task_id": task["id"],
                "status": submission["gurobi_result"].get("status"),
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
            "output_root": str(output_root),
        }
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
