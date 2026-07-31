from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from controlled_retrieval import FrozenBM25, read_jsonl
from run_codex_cli_one_shot import (
    audit_events,
    load_solver_backend,
    parse_events,
    prepare_context,
    run_one,
    safe_progress,
)
from run_prompt_baselines import (
    class_string_assignment,
    format_evidence,
    literal_assignment,
)


DEFAULT_ADAPTER_STAGE_TIMEOUT_SECONDS = 180
ADAPTER_STAGE_TIMEOUT_SECONDS = DEFAULT_ADAPTER_STAGE_TIMEOUT_SECONDS


def timeout_stream_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def audit_stage_events(
    events: list[dict[str, Any]],
    non_json_lines: list[str],
) -> dict[str, Any]:
    """Audit a compatibility-adapter stage without weakening one-shot audit."""
    audit = audit_events(events, non_json_lines)
    violations = []
    for violation in audit["violations"]:
        allow_multiple_messages = (
            violation.get("type") == "final_message_count"
            and int(violation.get("actual", 0)) >= 1
        )
        allow_internal_todo = (
            violation.get("type") == "forbidden_item"
            and violation.get("item_type") == "todo_list"
        )
        allow_trailing_todo = (
            violation.get("type") == "final_completed_item"
            and violation.get("actual") == "todo_list"
        )
        if not (allow_multiple_messages or allow_internal_todo or allow_trailing_todo):
            violations.append(violation)
    completed_items = [
        event
        for event in events
        if event.get("type") == "item.completed"
        and event.get("item", {}).get("type") != "error"
    ]
    completed_agent_indices = [
        index
        for index, event in enumerate(events)
        if event.get("type") == "item.completed"
        and event.get("item", {}).get("type") == "agent_message"
    ]
    trailing_internal_items: list[dict[str, Any]] = []
    if not completed_agent_indices:
        violations.append(
            {
                "type": "missing_completed_agent_message",
                "expected_at_least": 1,
                "actual": 0,
            }
        )
    else:
        last_agent_index = completed_agent_indices[-1]
        for event in events[last_agent_index + 1 :]:
            event_type = event.get("type", "")
            if not event_type.startswith("item."):
                continue
            item = event.get("item", {})
            item_type = item.get("type")
            trailing_item = {
                "event_type": event_type,
                "item_type": item_type,
                "item_id": item.get("id"),
            }
            trailing_internal_items.append(trailing_item)
            if item_type != "todo_list":
                violations.append(
                    {
                        "type": "post_final_agent_item",
                        **trailing_item,
                        "allowed_item_type": "todo_list",
                    }
                )
    last_completed_type = (
        completed_items[-1].get("item", {}).get("type")
        if completed_items
        else None
    )
    return {
        **audit,
        "passed": not violations,
        "violations": violations,
        "stage_multi_message_compatibility": True,
        "last_completed_non_error_item": last_completed_type,
        "completed_agent_message_count": len(completed_agent_indices),
        "todo_list_event_count": sum(
            1
            for event in events
            if event.get("type", "").startswith("item.")
            and event.get("item", {}).get("type") == "todo_list"
        ),
        "trailing_item_types": [
            item["item_type"] for item in trailing_internal_items
        ],
        "trailing_internal_items": trailing_internal_items,
    }


def call_json_stage(
    prompt: str,
    stage: str,
    artifact_dir: Path,
    sterile_dir: Path,
    codex_executable: str,
    output_schema: Path,
    model: str,
    reasoning_effort: str,
    reuse_existing_response: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    sterile_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = artifact_dir / f"{stage}.prompt.txt"
    response_path = artifact_dir / f"{stage}.response.json"
    events_path = artifact_dir / f"{stage}.events.jsonl"
    stderr_path = artifact_dir / f"{stage}.stderr.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    command = [
        codex_executable,
        "exec",
        "-m",
        model,
        "-c",
        f'model_reasoning_effort="{reasoning_effort}"',
        "-c",
        "features.shell_tool=false",
        "-c",
        'web_search="disabled"',
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
        str(response_path.resolve()),
        "-",
    ]
    if reuse_existing_response and response_path.exists():
        if not events_path.exists():
            raise RuntimeError(
                f"{stage} has an existing response without events; "
                "refusing to call the model again"
            )
        stdout_text = events_path.read_text(encoding="utf-8")
        stderr_text = (
            stderr_path.read_text(encoding="utf-8")
            if stderr_path.exists()
            else ""
        )
        returncode = 0
        elapsed = 0.0
        reused = True
    else:
        if reuse_existing_response:
            existing_events = (
                events_path.read_text(encoding="utf-8")
                if events_path.exists()
                else ""
            )
            existing_stderr = (
                stderr_path.read_text(encoding="utf-8")
                if stderr_path.exists()
                else ""
            )
            if existing_events.strip() or existing_stderr.strip():
                raise RuntimeError(
                    f"{stage} has existing events or stderr without a "
                    "response; refusing to call the model again"
                )
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=ADAPTER_STAGE_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            events_path.write_text(
                timeout_stream_text(exc.stdout), encoding="utf-8"
            )
            stderr_path.write_text(
                timeout_stream_text(exc.stderr), encoding="utf-8"
            )
            raise
        elapsed = time.perf_counter() - started
        stdout_text = completed.stdout
        stderr_text = completed.stderr
        returncode = completed.returncode
        reused = False
        events_path.write_text(stdout_text, encoding="utf-8")
        stderr_path.write_text(stderr_text, encoding="utf-8")
    events, usage, non_json_lines = parse_events(stdout_text)
    event_audit = audit_stage_events(events, non_json_lines)
    if returncode != 0:
        raise RuntimeError(
            f"{stage} CLI failed with code {returncode}"
        )
    if not event_audit["passed"]:
        raise RuntimeError(
            f"{stage} event audit failed: {event_audit['violations']}"
        )
    response: dict[str, Any] = json.loads(
        response_path.read_text(encoding="utf-8-sig")
    )
    return response, {
        "stage": stage,
        "usage": usage,
        "wall_seconds": elapsed,
        "cli_timeout_seconds": ADAPTER_STAGE_TIMEOUT_SECONDS,
        "event_audit": event_audit,
        "reused_existing_response": reused,
    }


def call_text_stage(
    prompt: str,
    stage: str,
    artifact_dir: Path,
    sterile_dir: Path,
    codex_executable: str,
    output_schema: Path,
    model: str,
    reasoning_effort: str,
    reuse_existing_response: bool = False,
) -> tuple[str, dict[str, Any]]:
    response, record = call_json_stage(
        prompt,
        stage,
        artifact_dir,
        sterile_dir,
        codex_executable,
        output_schema,
        model,
        reasoning_effort,
        reuse_existing_response,
    )
    return response["content"], record


def optimus_scratchpad(
    task: dict[str, Any],
    evidence: list[dict[str, Any]],
    task_dir: Path,
    sterile_dir: Path,
    codex_executable: str,
    text_schema: Path,
    model: str,
    reasoning_effort: str,
    optimus_root: Path,
    reuse_existing_response: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    description = (
        task["problem_zh"]
        + "\n\n外部证据候选：\n"
        + format_evidence(evidence)
    )
    params_prompt = literal_assignment(
        optimus_root / "parameters.py", "prompt_params"
    )
    objective_prompt = literal_assignment(
        optimus_root / "objective.py", "prompt_objective"
    )
    constraints_prompt = literal_assignment(
        optimus_root / "constraint.py", "prompt_constraints"
    )
    records = []
    params, record = call_text_stage(
        params_prompt.format(description=description),
        "optimus_parameters",
        task_dir,
        sterile_dir / "parameters",
        codex_executable,
        text_schema,
        model,
        reasoning_effort,
        reuse_existing_response,
    )
    records.append(record)
    objective, record = call_text_stage(
        objective_prompt.format(
            rag="",
            description=description,
            params=params,
        ),
        "optimus_objective",
        task_dir,
        sterile_dir / "objective",
        codex_executable,
        text_schema,
        model,
        reasoning_effort,
        reuse_existing_response,
    )
    records.append(record)
    constraints, record = call_text_stage(
        constraints_prompt.format(
            rag="",
            description=description,
            params=params,
        ),
        "optimus_constraints",
        task_dir,
        sterile_dir / "constraints",
        codex_executable,
        text_schema,
        model,
        reasoning_effort,
        reuse_existing_response,
    )
    records.append(record)
    return (
        "\n\n".join(
            [
                "[OPTIMUS parameters]\n" + params,
                "[OPTIMUS objective]\n" + objective,
                "[OPTIMUS constraints]\n" + constraints,
            ]
        ),
        records,
    )


def coe_scratchpad(
    task: dict[str, Any],
    evidence: list[dict[str, Any]],
    task_dir: Path,
    sterile_dir: Path,
    codex_executable: str,
    text_schema: Path,
    model: str,
    reasoning_effort: str,
    coe_root: Path,
    reuse_existing_response: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    roles = [
        ("ParameterExtractor", "parameter_extractor.py"),
        ("TerminologyInterpreter", "terminology_interpreter.py"),
        ("ModelingExpert", "modeling_expert.py"),
        ("ProgrammingExpert", "programming_expert.py"),
        ("CodeReviewer", "code_reviewer.py"),
    ]
    shared = (
        "任务：\n"
        + task["problem_zh"]
        + "\n\n证据候选：\n"
        + format_evidence(evidence)
    )
    transcripts = []
    records = []
    for class_name, filename in roles:
        role = class_string_assignment(
            coe_root / "experts" / filename,
            class_name,
            "ROLE_DESCRIPTION",
        )
        prompt = f"""{role}

你是 Chain-of-Experts 中的 {class_name}。只处理你的专业职责。
区分题面基础模型与证据造成的结构补丁，不得发明未提供的规则。

{shared}

此前专家输出：
{chr(10).join(transcripts) if transcripts else "无"}

返回给后续专家的紧凑工作记录。"""
        response, record = call_text_stage(
            prompt,
            f"coe_{class_name}",
            task_dir,
            sterile_dir / class_name,
            codex_executable,
            text_schema,
            model,
            reasoning_effort,
            reuse_existing_response,
        )
        records.append(record)
        transcripts.append(f"[{class_name}]\n{response}")
    return "\n\n".join(transcripts), records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--baseline",
        required=True,
        choices=["optimus_inspired", "coe_inspired"],
    )
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
        "--text-schema",
        default=Path("configs/cli_text_output_schema.json"),
        type=Path,
    )
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument(
        "--stage-timeout-seconds",
        type=int,
        default=DEFAULT_ADAPTER_STAGE_TIMEOUT_SECONDS,
        help="Per-stage Codex CLI timeout; defaults to 180 seconds for cross-shard fairness.",
    )
    parser.add_argument(
        "--optimus-root",
        default=Path(r"<LOCAL_BASELINES_ROOT>\OptiMUS-main"),
        type=Path,
    )
    parser.add_argument(
        "--coe-root",
        default=Path(r"<LOCAL_BASELINES_ROOT>\Chain-of-Experts-main"),
        type=Path,
    )
    parser.add_argument("--task-id", action="append")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.stage_timeout_seconds <= 0:
        raise ValueError("--stage-timeout-seconds must be a positive integer")
    global ADAPTER_STAGE_TIMEOUT_SECONDS
    ADAPTER_STAGE_TIMEOUT_SECONDS = args.stage_timeout_seconds

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
    codex_hash = hashlib.sha256(codex_path.read_bytes()).hexdigest()
    if args.baseline == "optimus_inspired":
        source_files = [
            args.optimus_root / filename
            for filename in (
                "parameters.py",
                "objective.py",
                "constraint.py",
            )
        ]
    else:
        source_files = [
            args.coe_root / "experts" / filename
            for filename in (
                "parameter_extractor.py",
                "terminology_interpreter.py",
                "modeling_expert.py",
                "programming_expert.py",
                "code_reviewer.py",
            )
        ]
    source_snapshot = [
        {
            "path": str(path.resolve()),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in source_files
    ]
    manifest_path = output_root / "run_manifest.json"
    if not (args.resume and args.task_id and manifest_path.exists()):
        manifest_path.write_text(
            json.dumps(
                {
                    "baseline": args.baseline,
                    "condition": args.condition,
                    "codex_path": str(codex_path),
                    "codex_sha256": codex_hash,
                    "model": args.model,
                    "reasoning_effort": args.reasoning_effort,
                    "adapter_not_upstream_unmodified": True,
                    "source_snapshot_is_non_git": True,
                    "source_files": source_snapshot,
                    "retries": 0,
                    "adapter_stage_timeout_seconds": (
                        ADAPTER_STAGE_TIMEOUT_SECONDS
                    ),
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
        evidence, search_trace = prepare_context(
            task, args.condition, evidence_index
        )
        try:
            if args.baseline == "optimus_inspired":
                scratchpad, stage_records = optimus_scratchpad(
                    task,
                    evidence,
                    task_dir,
                    sterile_root / task["id"],
                    str(codex_path),
                    args.text_schema,
                    args.model,
                    args.reasoning_effort,
                    args.optimus_root,
                    args.resume,
                )
                baseline_name = "optimus_inspired_cli_adapter"
            else:
                scratchpad, stage_records = coe_scratchpad(
                    task,
                    evidence,
                    task_dir,
                    sterile_root / task["id"],
                    str(codex_path),
                    args.text_schema,
                    args.model,
                    args.reasoning_effort,
                    args.coe_root,
                    args.resume,
                )
                baseline_name = "coe_inspired_cli_adapter"
            submission = run_one(
                task=task,
                condition=args.condition,
                documents=evidence,
                search_trace=search_trace,
                task_dir=task_dir,
                sterile_dir=sterile_root / task["id"] / "final",
                codex_executable=str(codex_path),
                python_executable=args.python,
                output_schema=args.final_schema,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                solver_backend=solver_backend,
                baseline=baseline_name,
                scratchpad=scratchpad,
                reuse_existing_response=args.resume,
            )
            submission["usage"]["adapter_stages"] = stage_records
            submission["usage"]["adapter_stage_count"] = len(
                stage_records
            )
            (task_dir / "submission.json").write_text(
                json.dumps(
                    submission, ensure_ascii=False, indent=2
                )
                + "\n",
                encoding="utf-8",
            )
            submissions.append(submission)
            if args.resume and existing_failure.exists():
                (task_dir / "resume_resolution.json").write_text(
                    json.dumps(
                        {
                            "status": "recovered_from_existing_stage_artifacts",
                            "stale_failure_file_preserved": "failure.json",
                            "reused_stages": [
                                record["stage"]
                                for record in stage_records
                                if record.get("reused_existing_response")
                            ],
                            "newly_called_stages": [
                                record["stage"]
                                for record in stage_records
                                if not record.get(
                                    "reused_existing_response"
                                )
                            ],
                            "final_model_response_reused": submission[
                                "usage"
                            ].get(
                                "reused_existing_model_response",
                                False,
                            ),
                            "model_calls_during_resume": (
                                sum(
                                    not record.get(
                                        "reused_existing_response"
                                    )
                                    for record in stage_records
                                )
                                + int(
                                    not submission["usage"].get(
                                        "reused_existing_model_response",
                                        False,
                                    )
                                )
                            ),
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
                    "status": submission["gurobi_result"].get("status"),
                }
            )
        except Exception as exc:  # noqa: BLE001 - experiment artifact
            failure = {
                "task_id": task["id"],
                "type": type(exc).__name__,
                "message": str(exc),
            }
            failures.append(failure)
            task_dir.mkdir(parents=True, exist_ok=True)
            failure_path = (
                task_dir / "recovery_failure_attempt1.json"
                if args.resume and existing_failure.exists()
                else task_dir / "failure.json"
            )
            failure_path.write_text(
                json.dumps(failure, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            if args.resume and existing_failure.exists():
                (task_dir / "resume_resolution.json").write_text(
                    json.dumps(
                        {
                            "status": "recovery_failed_no_further_retry",
                            "stale_failure_file_preserved": "failure.json",
                            "recovery_failure_file": failure_path.name,
                            "newly_completed_stages": [
                                record["stage"]
                                for record in stage_records
                                if not record.get("reused_existing_response")
                            ],
                            "failure_message": str(exc),
                            "submission_created": False,
                            "retry_exhausted": True,
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
