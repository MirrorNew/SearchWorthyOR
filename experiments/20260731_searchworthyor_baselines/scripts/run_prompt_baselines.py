from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

from controlled_retrieval import FrozenBM25, read_jsonl
from llm_api import LLMConfig, StrictReasoningClient


FINAL_SYSTEM = """You are an operations-research modeling expert.
Return a single JSON object and no prose. Build a single-objective binary MILP.
Use the candidate order in the task as x_0, x_1, ... and keep that order in
action_projection. External evidence may change model structure only when you
have selected an applicable authoritative rule. Produce executable gurobipy
code that prints a JSON object with status, objective, projected_action,
max_constraint_violation, and integrality_violation. Do not invent missing
evidence. Do not use network or file access in generated code."""


def load_solver_backend(dataset_root: Path):
    path = dataset_root / "scripts" / "solver_backend.py"
    spec = importlib.util.spec_from_file_location("searchworthyor_solver_backend", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def literal_assignment(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    value = ast.literal_eval(node.value)
                    if isinstance(value, str):
                        return value
    raise KeyError(f"{name} not found in {path}")


def class_string_assignment(path: Path, class_name: str, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in node.body:
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Name) and target.id == name:
                            value = ast.literal_eval(child.value)
                            if isinstance(value, str):
                                return value
    raise KeyError(f"{class_name}.{name} not found in {path}")


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", stripped, flags=re.DOTALL)
    candidates = fenced + [stripped]
    decoder = json.JSONDecoder()
    for candidate in candidates:
        for index, char in enumerate(candidate):
            if char != "{":
                continue
            try:
                value, _ = decoder.raw_decode(candidate[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
    raise ValueError("No JSON object found in model response.")


def format_evidence(documents: list[dict[str, Any]]) -> str:
    if not documents:
        return "未提供外部证据。"
    blocks = []
    for document in documents:
        blocks.append(f"[{document['id']}]\n{document['content']}")
    return "\n\n".join(blocks)


def final_user_prompt(
    task: dict[str, Any],
    evidence_documents: list[dict[str, Any]],
    scratchpad: str,
) -> str:
    schema = {
        "selected_evidence_ids": ["DOC-..."],
        "applicability": {
            "authority": True,
            "effective_at_decision_time": True,
            "jurisdiction_match": True,
            "subject_match": True,
            "exception_resolved": True,
            "reason": "...",
        },
        "base_ir": {
            "model_id": "TASK_base",
            "world": "base",
            "sense": "max",
            "single_objective": True,
            "variables": [
                {
                    "name": "x_0",
                    "vartype": "B",
                    "lb": 0,
                    "ub": 1,
                    "semantic_name": "候选A",
                }
            ],
            "objective": {"constant": 0, "terms": {"x_0": 1}},
            "constraints": [
                {
                    "name": "c0",
                    "sense": "<=",
                    "rhs": 1,
                    "terms": {"x_0": 1},
                }
            ],
            "action_projection": ["x_0"],
        },
        "typed_patch": {
            "ops": [
                {
                    "op": "add_constraint",
                    "slot_type": "constraint",
                    "evidence_claim": "...",
                    "before_expression": "<absent>",
                    "after_expression": "1*x_0 <= 0",
                }
            ]
        },
        "patched_ir": "<same IR schema as base_ir>",
        "gurobi_code": "complete Python source string",
        "claim_to_model_mapping": [
            {
                "evidence_id": "DOC-...",
                "claim": "...",
                "model_slot": "...",
                "equation": "...",
                "code_region": "...",
            }
        ],
    }
    return f"""任务：
{task["problem_zh"]}

决策时间：{task["decision_time"]}
实体：{task["entity"]}
辖区：{task["jurisdiction"]}

可用证据：
{format_evidence(evidence_documents)}

此前各阶段的工作记录：
{scratchpad or "无"}

请独立核对题面、证据适用性和工作记录。输出必须符合以下 JSON 结构；示例只说明字段，
不得复制示例中的数字或约束：
{json.dumps(schema, ensure_ascii=False, indent=2)}

base_ir 必须只表达题面冻结的基础模型；patched_ir 必须是采用适用证据后的最终模型。
若未得到足够证据，二者可以相同并在 applicability.reason 中明确说明。两个 IR 都必须
包含完整目标、变量、约束和 action_projection。gurobi_code 必须完整、自包含、只使用
gurobipy/json/math，必须求解 patched_ir 对应模型并输出机器可读 JSON。"""


def prepare_context(
    condition: str,
    task: dict[str, Any],
    evidence_index: FrozenBM25,
    evidence_by_id: dict[str, dict[str, Any]],
    gold_by_id: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if condition == "no_search":
        return [], []
    if condition == "corpus_search":
        query = " ".join(
            [task["entity"], task["jurisdiction"], task["decision_time"]]
        )
        results = evidence_index.search(query, 5)
        trace = [
            {
                "query": query,
                "results": [
                    {"rank": rank, "id": row["id"], "score": row["score"]}
                    for rank, row in enumerate(results, 1)
                ],
            }
        ]
        return results, trace
    if condition == "oracle_evidence":
        evidence_id = gold_by_id[task["id"]]["applicability"]["selected_evidence_id"]
        return [evidence_by_id[evidence_id]], [
            {
                "query": "<oracle-evidence>",
                "results": [{"rank": 1, "id": evidence_id, "score": 1.0}],
            }
        ]
    raise ValueError(f"Unsupported condition: {condition}")


def call_and_record(
    client: StrictReasoningClient,
    messages: list[dict[str, str]],
    calls: list[dict[str, Any]],
    stage: str,
) -> str:
    result = client.complete(messages)
    calls.append(
        {
            "stage": stage,
            "requested_model": result["requested_model"],
            "actual_model": result["actual_model"],
            "requested_reasoning_effort": result["requested_reasoning_effort"],
            "reasoning_fallback": result["reasoning_fallback"],
            "usage": result["usage"],
            "request_id": result["request_id"],
            "elapsed_seconds": result["elapsed_seconds"],
        }
    )
    return result["content"]


def run_one_shot(
    client: StrictReasoningClient,
    task: dict[str, Any],
    evidence: list[dict[str, Any]],
    calls: list[dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    prompt = final_user_prompt(task, evidence, "")
    response = call_and_record(
        client,
        [
            {"role": "system", "content": FINAL_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        calls,
        "one_shot",
    )
    return extract_json_object(response), response


def run_optimus_prompt(
    client: StrictReasoningClient,
    task: dict[str, Any],
    evidence: list[dict[str, Any]],
    calls: list[dict[str, Any]],
    optimus_root: Path,
) -> tuple[dict[str, Any], str]:
    description = (
        task["problem_zh"] + "\n\n外部证据候选：\n" + format_evidence(evidence)
    )
    params_prompt = literal_assignment(optimus_root / "parameters.py", "prompt_params")
    objective_prompt = literal_assignment(
        optimus_root / "objective.py", "prompt_objective"
    )
    constraints_prompt = literal_assignment(
        optimus_root / "constraint.py", "prompt_constraints"
    )
    params = call_and_record(
        client,
        [{"role": "user", "content": params_prompt.format(description=description)}],
        calls,
        "optimus_parameters",
    )
    objective = call_and_record(
        client,
        [
            {
                "role": "user",
                "content": objective_prompt.format(
                    rag="",
                    description=description,
                    params=params,
                ),
            }
        ],
        calls,
        "optimus_objective",
    )
    constraints = call_and_record(
        client,
        [
            {
                "role": "user",
                "content": constraints_prompt.format(
                    rag="",
                    description=description,
                    params=params,
                ),
            }
        ],
        calls,
        "optimus_constraints",
    )
    scratchpad = (
        "OPTIMUS parameter stage:\n"
        + params
        + "\n\nOPTIMUS objective stage:\n"
        + objective
        + "\n\nOPTIMUS constraint stage:\n"
        + constraints
    )
    final_prompt = final_user_prompt(task, evidence, scratchpad)
    response = call_and_record(
        client,
        [
            {"role": "system", "content": FINAL_SYSTEM},
            {"role": "user", "content": final_prompt},
        ],
        calls,
        "optimus_formulation_and_code",
    )
    return extract_json_object(response), response


def run_chain_of_experts(
    client: StrictReasoningClient,
    task: dict[str, Any],
    evidence: list[dict[str, Any]],
    calls: list[dict[str, Any]],
    coe_root: Path,
) -> tuple[dict[str, Any], str]:
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
    for class_name, filename in roles:
        role = class_string_assignment(
            coe_root / "experts" / filename, class_name, "ROLE_DESCRIPTION"
        )
        prompt = f"""{role}

你是 Chain-of-Experts 中的 {class_name}。只处理你的专业职责，并检查此前专家输出。
必须区分题面基础模型与证据造成的结构补丁。不得假设未提供的证据。

{shared}

此前专家输出：
{chr(10).join(transcripts) if transcripts else "无"}

返回给后续专家的紧凑工作记录。"""
        response = call_and_record(
            client,
            [{"role": "user", "content": prompt}],
            calls,
            f"coe_{class_name}",
        )
        transcripts.append(f"[{class_name}]\n{response}")
    final_prompt = final_user_prompt(task, evidence, "\n\n".join(transcripts))
    response = call_and_record(
        client,
        [
            {"role": "system", "content": FINAL_SYSTEM},
            {"role": "user", "content": final_prompt},
        ],
        calls,
        "coe_reducer",
    )
    return extract_json_object(response), response


def replay_prediction(prediction: dict[str, Any], solver_backend: Any) -> dict[str, Any]:
    ir = prediction.get("patched_ir")
    if not isinstance(ir, dict):
        return {"status": "ERROR", "error": "missing patched_ir"}
    try:
        return solver_backend.solve_gurobi(ir)
    except Exception as exc:  # noqa: BLE001 - experiment artifact
        return {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"}


def run_task(
    baseline: str,
    condition: str,
    task: dict[str, Any],
    evidence: list[dict[str, Any]],
    search_trace: list[dict[str, Any]],
    client: StrictReasoningClient,
    solver_backend: Any,
    optimus_root: Path,
    coe_root: Path,
) -> tuple[dict[str, Any], str]:
    calls: list[dict[str, Any]] = []
    started = time.perf_counter()
    if baseline == "gpt56_one_shot":
        prediction, raw = run_one_shot(client, task, evidence, calls)
    elif baseline == "optimus_prompt":
        prediction, raw = run_optimus_prompt(
            client, task, evidence, calls, optimus_root
        )
    elif baseline == "chain_of_experts":
        prediction, raw = run_chain_of_experts(
            client, task, evidence, calls, coe_root
        )
    else:
        raise ValueError(f"Unsupported baseline: {baseline}")
    gurobi_result = replay_prediction(prediction, solver_backend)
    first_call = calls[0]
    actual_models = sorted(
        {str(call["actual_model"]) for call in calls if call["actual_model"]}
    )
    result = {
        "task_id": task["id"],
        "baseline": baseline,
        "condition": condition,
        "requested_model": first_call["requested_model"],
        "actual_model": actual_models,
        "requested_reasoning_effort": first_call["requested_reasoning_effort"],
        "reasoning_fallback": any(call["reasoning_fallback"] for call in calls),
        "generated_once": baseline == "gpt56_one_shot",
        "search_trace": search_trace,
        "selected_evidence_ids": prediction.get("selected_evidence_ids", []),
        "applicability": prediction.get("applicability", {}),
        "base_ir": prediction.get("base_ir"),
        "typed_patch": prediction.get("typed_patch", {"ops": []}),
        "patched_ir": prediction.get("patched_ir"),
        "gurobi_code": prediction.get("gurobi_code", ""),
        "gurobi_result": gurobi_result,
        "claim_to_model_mapping": prediction.get("claim_to_model_mapping", []),
        "usage": {
            "calls": calls,
            "call_count": len(calls),
            "wall_seconds": time.perf_counter() - started,
        },
    }
    return result, raw


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--baseline",
        required=True,
        choices=["gpt56_one_shot", "optimus_prompt", "chain_of_experts"],
    )
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
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--optimus-root", type=Path, default=Path(r"<LOCAL_BASELINES_ROOT>\OptiMUS-main")
    )
    parser.add_argument(
        "--coe-root",
        type=Path,
        default=Path(r"<LOCAL_BASELINES_ROOT>\Chain-of-Experts-main"),
    )
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
    evidence_index = FrozenBM25(evidence_rows)
    if args.condition == "oracle_evidence":
        gold_rows = read_jsonl(args.dataset_root / "private" / "gold.jsonl")
        gold_by_id = {row["id"]: row for row in gold_rows}
    else:
        gold_by_id = {}
    solver_backend = load_solver_backend(args.dataset_root)
    client = StrictReasoningClient(
        LLMConfig.from_environment(args.model, args.reasoning_effort)
    )

    run_dir = args.output_dir / args.baseline / args.condition
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
        evidence, search_trace = prepare_context(
            args.condition,
            task,
            evidence_index,
            evidence_by_id,
            gold_by_id,
        )
        try:
            submission, raw = run_task(
                args.baseline,
                args.condition,
                task,
                evidence,
                search_trace,
                client,
                solver_backend,
                args.optimus_root,
                args.coe_root,
            )
            status = "ok"
        except Exception as exc:  # noqa: BLE001 - preserve failure as result
            submission = {
                "task_id": task["id"],
                "baseline": args.baseline,
                "condition": args.condition,
                "requested_model": args.model,
                "actual_model": [],
                "requested_reasoning_effort": args.reasoning_effort,
                "reasoning_fallback": False,
                "generated_once": args.baseline == "gpt56_one_shot",
                "search_trace": search_trace,
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
                "usage": {},
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
