from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

from candidate_adapter import execute_candidate, explicit_applicability_and_patch, normalize_capture
from common import (
    EXPERIMENT_ROOT,
    MODEL,
    REASONING_EFFORT,
    TEMPERATURE,
    StrictAPIClient,
    StrictAPIRequestError,
    ConfigurationViolation,
    GlobalStopError,
    load_config,
    public_cases,
    output_schema_for,
    selected_ids,
    summarize_calls,
    unified_output,
    validate_formal_gate,
    write_json,
)


PYTHON = Path(os.environ.get("SWOR_PYTHON", sys.executable))
OPTIMUS_ROOT = Path(os.environ.get("OPTIMUS_ROOT", r"D:\LLMProject\OptiMUS-main"))
COE_ROOT = Path(os.environ.get("COE_ROOT", r"D:\LLMProject\Chain-of-Experts-main"))
RUN_ROOT = EXPERIMENT_ROOT / "runs"
METHODS = {"coe": "CoE", "optimus": "OptiMUS"}


def render_problem(public: dict[str, Any]) -> str:
    return str(public["prompt_zh"]).strip()


def clear_framework_modules(root: Path) -> None:
    root_text = str(root.resolve()).lower()
    for name, module in list(sys.modules.items()):
        filename = getattr(module, "__file__", None)
        if isinstance(filename, str) and str(Path(filename).resolve()).lower().startswith(root_text):
            sys.modules.pop(name, None)


def run_optimus(task_id: str, problem: str, attempt_dir: Path, client: StrictAPIClient) -> dict[str, Any]:
    clear_framework_modules(OPTIMUS_ROOT)
    sys.path.insert(0, str(OPTIMUS_ROOT))
    try:
        import utils as optimus_utils

        def provider_get_response(prompt: str, model: str = MODEL) -> str:
            del model
            return str(client.complete([{"role": "user", "content": prompt}], "optimus_native_agent")["content"])

        optimus_utils.get_response = provider_get_response
        import generate_code
        import optimus_tools

        optimus_tools.MODEL = MODEL
        native_dir = attempt_dir / "native"
        native_dir.mkdir(parents=True, exist_ok=True)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stdout):
            state = optimus_tools.get_intro_latex_code_map(
                None,
                desc=problem,
                origin_path=str(native_dir),
                idx=task_id,
            )
            write_json(attempt_dir / "data.json", state)
            code = generate_code.generate_code(state, "", None)
        (attempt_dir / "framework_stdout.txt").write_text(stdout.getvalue(), encoding="utf-8")
        write_json(attempt_dir / "native_state.json", state)
        (attempt_dir / "native_answer.txt").write_text(str(code), encoding="utf-8")
        return {"answer": None, "code": str(code), "native_entrypoint": "optimus_tools.get_intro_latex_code_map + generate_code.generate_code"}
    finally:
        if sys.path and sys.path[0] == str(OPTIMUS_ROOT):
            sys.path.pop(0)


def strict_langchain_factory(client: StrictAPIClient):
    from langchain.llms.base import LLM

    class StrictLangChainLLM(LLM):
        max_tokens: Optional[int] = None

        @property
        def _llm_type(self) -> str:
            return "searchworthyor_exact_provider"

        @property
        def _identifying_params(self) -> dict[str, Any]:
            return {"model": MODEL, "reasoning_effort": REASONING_EFFORT, "temperature": TEMPERATURE}

        def _call(self, prompt: str, stop: Optional[list[str]] = None, run_manager: Any = None, **kwargs: Any) -> str:
            del run_manager, kwargs
            text = str(client.complete([{"role": "user", "content": prompt}], "coe_native_agent")["content"])
            for marker in stop or []:
                if marker in text:
                    text = text.split(marker, 1)[0]
            return text

    if hasattr(StrictLangChainLLM, "model_rebuild"):
        StrictLangChainLLM.model_rebuild(_types_namespace={"Optional": Optional, "Any": Any})

    def factory(*args: Any, **kwargs: Any):
        del args
        return StrictLangChainLLM(max_tokens=kwargs.get("max_tokens"))

    return factory


def coe_code_example(task_id: str) -> str:
    suffix = task_id.lower().replace("-", "_")
    return f'''```python
import gurobipy as gp
from gurobipy import GRB

def case_{suffix}():
    model = gp.Model()
    # To be implemented by the native workflow.
    return obj

obj = case_{suffix}()
print(obj)
print(f"FinalAnswer=【theFinalAnswer】{{obj}}")
```'''


def run_coe(task_id: str, problem: str, attempt_dir: Path, client: StrictAPIClient) -> dict[str, Any]:
    clear_framework_modules(COE_ROOT)
    sys.path.insert(0, str(COE_ROOT))
    try:
        import main as coe_main
        from experts import base_expert
        import integrated_runner
        import utils as coe_utils

        factory = strict_langchain_factory(client)
        root_text = str(COE_ROOT.resolve()).lower()
        for module in list(sys.modules.values()):
            filename = getattr(module, "__file__", None)
            if isinstance(filename, str) and str(Path(filename).resolve()).lower().startswith(root_text) and hasattr(module, "ChatOpenAI"):
                setattr(module, "ChatOpenAI", factory)
        base_expert.BaseExpert.total_usage.clear()
        problem_data = {"description": problem, "code_example": coe_code_example(task_id)}
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stdout):
            answer = coe_main.chain_of_experts(
                problem_data,
                max_collaborate_nums=3,
                model_name=MODEL,
                enable_reflection=False,
                max_trials=1,
            )
        raw_code = coe_utils.extract_code_from_string(answer)
        code = integrated_runner.apply_run_final_like_fixes(raw_code)
        (attempt_dir / "framework_stdout.txt").write_text(stdout.getvalue(), encoding="utf-8")
        (attempt_dir / "native_answer.txt").write_text(str(answer), encoding="utf-8")
        return {"answer": str(answer), "code": str(code), "native_entrypoint": "main.chain_of_experts"}
    finally:
        if sys.path and sys.path[0] == str(COE_ROOT):
            sys.path.pop(0)


def framework_call(method: str, task_id: str, public: dict[str, Any], attempt_dir: Path, client: StrictAPIClient) -> dict[str, Any]:
    problem = render_problem(public)
    if method == "optimus":
        return run_optimus(task_id, problem, attempt_dir, client)
    return run_coe(task_id, problem, attempt_dir, client)


def runner_retryable(exc: BaseException, calls: dict[str, Any]) -> bool:
    return calls.get("calls") == 0 and isinstance(exc, (ImportError, ModuleNotFoundError, OSError))


def run_one(method: str, phase: str, task_id: str) -> dict[str, Any]:
    method_name = METHODS[method]
    public = public_cases()[task_id]
    task_dir = RUN_ROOT / phase / method / task_id
    output_path = task_dir / "unified_output.json"
    if output_path.is_file():
        return json.loads(output_path.read_text(encoding="utf-8"))
    task_dir.mkdir(parents=True, exist_ok=True)
    existing_attempts = sorted(path for path in task_dir.glob("attempt_*") if path.is_dir())
    if len(existing_attempts) >= 2:
        output = unified_output(
            method=method_name,
            phase=phase,
            public=public,
            flags={"runner_failure": True},
            failure_detail="two interrupted attempts exist; refusing a third attempt",
            accounting=summarize_calls(existing_attempts[-1] / "api_calls.jsonl"),
        )
        write_json(output_path, output)
        return output

    started = time.perf_counter()
    flags: dict[str, bool] = {}
    failure_detail: str | None = None
    applicability = None
    patch = None
    actions = None
    objective = None
    solver_status = "NOT_STARTED"
    native_artifacts: dict[str, str] = {}
    accounting: dict[str, Any] = {}
    for attempt in range(len(existing_attempts) + 1, 3):
        attempt_dir = task_dir / f"attempt_{attempt}"
        attempt_dir.mkdir(parents=True, exist_ok=False)
        client = StrictAPIClient.from_environment(attempt_dir, method_name, task_id)
        try:
            native = framework_call(method, task_id, public, attempt_dir, client)
            code = str(native["code"])
            (attempt_dir / "generated_code.py").write_text(code, encoding="utf-8")
            execution = execute_candidate(code, attempt_dir)
            write_json(attempt_dir / "candidate_execution.json", execution)
            normalized = normalize_capture(
                output_schema_for(public),
                execution,
                final_answer=native.get("answer"),
                generated_code=code,
            )
            write_json(attempt_dir / "candidate_normalized.json", normalized)
            applicability, patch = explicit_applicability_and_patch(native.get("answer"))
            actions = normalized["actions"]
            objective = normalized["objective"]
            capture = execution.get("capture") if isinstance(execution, dict) else None
            solver_status = (
                "OPTIMAL"
                if execution.get("status") == "success" and isinstance(capture, dict) and capture.get("status") == 2
                else str(execution.get("status") or "EXECUTION_FAILURE").upper()
            )
            if execution.get("status") != "success":
                flags["parse_failure"] = True
                failure_detail = f"generated candidate execution status: {execution.get('status')}"
            native_artifacts = {
                "attempt_dir": str(attempt_dir),
                "entrypoint": str(native["native_entrypoint"]),
                "action_mapping": str(normalized["action_mapping"]),
            }
            accounting = summarize_calls(attempt_dir / "api_calls.jsonl")
            break
        except (ConfigurationViolation, GlobalStopError):
            raise
        except StrictAPIRequestError as exc:
            flags["provider_failure"] = True
            failure_detail = str(exc)
            accounting = summarize_calls(attempt_dir / "api_calls.jsonl")
            break
        except (SyntaxError, ValueError) as exc:
            flags["parse_failure"] = True
            failure_detail = f"{type(exc).__name__}: {str(exc)[:900]}"
            accounting = summarize_calls(attempt_dir / "api_calls.jsonl")
            (attempt_dir / "error_traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
            break
        except Exception as exc:
            call_summary = summarize_calls(attempt_dir / "api_calls.jsonl")
            (attempt_dir / "error_traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
            if attempt == 1 and runner_retryable(exc, call_summary):
                continue
            flags["runner_failure"] = True
            failure_detail = f"{type(exc).__name__}: {str(exc)[:900]}"
            accounting = call_summary
            break
    accounting["wall_total_seconds"] = time.perf_counter() - started
    output = unified_output(
        method=method_name,
        phase=phase,
        public=public,
        applicability=applicability,
        patch_elements=patch,
        actions=actions,
        objective=objective,
        flags=flags,
        failure_detail=failure_detail,
        native_artifacts=native_artifacts,
        accounting=accounting,
        solver_status=solver_status,
        attempt=attempt,
    )
    output["answer_present"] = isinstance(actions, list) and isinstance(objective, dict)
    output["native_web_search_allowed"] = False
    write_json(output_path, output)
    return output


def summary(method: str, phase: str, ids: list[str]) -> dict[str, Any]:
    outputs = []
    for task_id in ids:
        path = RUN_ROOT / phase / method / task_id / "unified_output.json"
        if path.is_file():
            outputs.append(json.loads(path.read_text(encoding="utf-8")))
    counts: dict[str, int] = {}
    for output in outputs:
        counts[output["status"]] = counts.get(output["status"], 0) + 1
    return {"method": METHODS[method], "phase": phase, "expected": len(ids), "completed": len(outputs), "status_counts": counts}


def run_worker(method: str, phase: str, task_id: str) -> tuple[str, int, str]:
    env = os.environ.copy()
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
    script = str(Path(__file__).resolve())
    bootstrap = "import runpy,sys;script=sys.argv.pop(1);sys.path.insert(0,script.rsplit('\\\\',1)[0]);sys.argv=[script,*sys.argv[1:]];runpy.run_path(script,run_name='__main__')"
    completed = subprocess.run(
        [str(PYTHON), "-I", "-c", bootstrap, script, "--method", method, "--phase", phase, "--worker-one", "--task-id", task_id],
        cwd=str(EXPERIMENT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return task_id, completed.returncode, completed.stdout[-4000:]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run V1.5.1 faithful local CoE or OptiMUS baseline without web search.")
    parser.add_argument("--method", choices=sorted(METHODS), required=True)
    parser.add_argument("--phase", choices=["smoke", "formal"], required=True)
    parser.add_argument("--task-ids", default="")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--worker-one", action="store_true")
    args = parser.parse_args()
    load_config()
    required = [PYTHON, OPTIMUS_ROOT / "optimus_tools.py"] if args.method == "optimus" else [PYTHON, COE_ROOT / "main.py"]
    for path in required:
        if not path.exists():
            raise FileNotFoundError(path)
    if args.phase == "formal":
        if args.task_ids or args.task_id:
            raise SystemExit("Formal CoE/OptiMUS must run all fixed 240 cases; subsets are forbidden")
        validate_formal_gate()
    if args.worker_one:
        if not args.task_id:
            raise SystemExit("--worker-one requires --task-id")
        output = run_one(args.method, args.phase, args.task_id)
        print(json.dumps({"task_id": args.task_id, "status": output["status"]}, ensure_ascii=False))
        return 0
    ids = selected_ids(args.phase, args.task_ids)
    if not 1 <= args.workers <= 10:
        raise SystemExit("local baseline workers must be between 1 and 10")
    error_log = RUN_ROOT / args.phase / args.method / "runner_errors.log"
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(run_worker, args.method, args.phase, task_id): task_id for task_id in ids}
        for done, future in enumerate(as_completed(futures), start=1):
            task_id, returncode, output = future.result()
            snapshot = summary(args.method, args.phase, ids)
            write_json(RUN_ROOT / args.phase / args.method / "summary.json", snapshot)
            print(json.dumps({"completed_processes": done, "task_id": task_id, "returncode": returncode, **snapshot}, ensure_ascii=False), flush=True)
            if returncode != 0:
                error_log.parent.mkdir(parents=True, exist_ok=True)
                with error_log.open("a", encoding="utf-8") as handle:
                    handle.write(f"[{task_id}] returncode={returncode}\n{output}\n")
    final = summary(args.method, args.phase, ids)
    write_json(RUN_ROOT / args.phase / args.method / "summary.json", final)
    print(json.dumps(final, ensure_ascii=False))
    return 0 if final["completed"] == len(ids) else 1


if __name__ == "__main__":
    raise SystemExit(main())
