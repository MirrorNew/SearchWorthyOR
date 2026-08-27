from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from candidate_adapter import execute_candidate, explicit_applicability_and_patch, normalize_capture
from common import (
    EXPERIMENT_ROOT,
    MODEL,
    REASONING_EFFORT,
    TEMPERATURE,
    WORKFLOW_ROOT,
    StrictAPIClient,
    StrictProxyServer,
    ConfigurationViolation,
    GlobalStopError,
    load_config,
    public_cases,
    output_schema_for,
    read_json,
    read_jsonl,
    selected_ids,
    summarize_calls,
    unified_output,
    validate_formal_gate,
    write_json,
    write_jsonl,
)


PYTHON = Path(os.environ.get("SWOR_PYTHON", sys.executable))
ORIGINAL_RUNNER = Path(
    os.environ.get("OPTIMINER_RUNNER", str(WORKFLOW_ROOT / "run_optminer_training_free.py"))
)
PACKET_PATH = EXPERIMENT_ROOT / "inputs" / "optiminer_benchmark.jsonl"
MAPPING_PATH = EXPERIMENT_ROOT / "inputs" / "optiminer_mapping.json"
RUN_ROOT = EXPERIMENT_ROOT / "runs"
ALIAS_DRIVE = "S:"
ALIAS_ROOT = Path("S:/")
PHYSICAL_SHORT_ROOT = EXPERIMENT_ROOT / "runs" / "_native_work"
SHORT_ROOT = ALIAS_ROOT / "runs" / "_native_work"
METHOD = "optiminer-training-free"


def current_alias_target() -> Path | None:
    completed = subprocess.run(
        ["subst.exe"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    prefix = f"{ALIAS_DRIVE}\\: => ".casefold()
    for line in completed.stdout.splitlines():
        if line.casefold().startswith(prefix):
            return Path(line.split("=>", 1)[1].strip())
    return None


def ensure_native_alias() -> bool:
    target = current_alias_target()
    if target is not None:
        if str(target.resolve()).casefold() != str(EXPERIMENT_ROOT.resolve()).casefold():
            raise RuntimeError(f"{ALIAS_DRIVE} is already mapped to another target")
        return False
    completed = subprocess.run(
        ["subst.exe", ALIAS_DRIVE, str(EXPERIMENT_ROOT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0 or current_alias_target() is None:
        raise RuntimeError(f"failed to create experiment-local path alias: {completed.stderr[-500:]}")
    return True


def release_native_alias(created: bool) -> None:
    if not created:
        return
    completed = subprocess.run(
        ["subst.exe", ALIAS_DRIVE, "/D"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        raise RuntimeError(f"failed to remove experiment-local path alias: {completed.stderr[-500:]}")


def inputs() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]]]:
    packet = {str(row["id"]): row for row in read_jsonl(PACKET_PATH)}
    mapping_payload = read_json(MAPPING_PATH)
    mapping = {str(row["task_id"]): row for row in mapping_payload["rows"]}
    if len(packet) != 240 or len(mapping) != 240:
        raise ValueError("V1.5.1 optiminer packet and mapping must contain 240 case rows")
    return packet, mapping


def proxy_context(attempt_dir: Path, task_id: str) -> tuple[StrictProxyServer, threading.Thread, str]:
    capability = secrets.token_urlsafe(32)
    client = StrictAPIClient.from_environment(attempt_dir, METHOD, task_id)
    server = StrictProxyServer(("127.0.0.1", 0), client, capability)
    thread = threading.Thread(target=server.serve_forever, name=f"optiminer-proxy-{task_id}", daemon=True)
    thread.start()
    return server, thread, capability


def child_environment(capability: str) -> dict[str, str]:
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("OPENOR_") or key.startswith("OPENAI_") or key in {"PYTHONPATH", "PYTHONHOME"}:
            env.pop(key, None)
    env.update(
        {
            "OPENOR_API_KEY": capability,
            "OPENOR_MODEL": MODEL,
            "OPENOR_SUMMARY_MODEL": MODEL,
            "OPENOR_REASONING_EFFORT": REASONING_EFFORT,
            "OPENOR_TEMPERATURE": "1",
            "OPENOR_TOP_P": "0.8",
            "OPENOR_TOP_K": "20",
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "NO_PROXY": "127.0.0.1,localhost,::1",
            "no_proxy": "127.0.0.1,localhost,::1",
        }
    )
    return env


def runner_command(attempt_dir: Path, benchmark: Path, runner_id: str, native_root: Path, base_url: str) -> list[str]:
    empty_config = attempt_dir / "empty_config.json"
    write_json(empty_config, {})
    bootstrap = (
        "import runpy,sys;"
        "root=sys.argv.pop(1);"
        "script=sys.argv.pop(1);"
        "sys.path.insert(0,root);"
        "sys.argv=[script,*sys.argv[1:]];"
        "runpy.run_path(script,run_name='__main__')"
    )
    return [
        str(PYTHON), "-X", "utf8", "-I", "-c", bootstrap, str(WORKFLOW_ROOT), str(ORIGINAL_RUNNER),
        "--config", str(empty_config),
        "--benchmark", str(benchmark),
        "--expansion-ids", runner_id,
        "--llm-provider", "openai",
        "--model", MODEL,
        "--summary-model", MODEL,
        "--base-url", base_url,
        "--temperature", "1",
        "--top-p", "0.8",
        "--top-k", "20",
        "--reasoning-effort", REASONING_EFFORT,
        "--llm-timeout-s", "650",
        "--workflow-mode", "agent_loop",
        "--max-research-turns", "3",
        "--max-agent-steps", "12",
        "--parse-repair-retries", "0",
        "--debug-retries", "0",
        "--search-results", "10",
        "--search-backend", "arxiv_document",
        "--document-extractor", "local_pdf",
        "--fetch-documents",
        "--search-timeout-s", "15",
        "--search-retries", "0",
        "--llm-retries", "0",
        "--retry-sleep-s", "8",
        "--format-repair-retries", "0",
        "--execution-timeout-s", "60",
        "--workers", "1",
        "--resume",
        "--run-root", str(native_root),
        "--out-json", str(attempt_dir / "native_eval.json"),
        "--out-csv", str(attempt_dir / "native_eval.csv"),
        "--out-md", str(attempt_dir / "native_eval.md"),
    ]


def short_native_root(phase: str, task_id: str, attempt: int) -> Path:
    root = SHORT_ROOT / phase / task_id / f"a{attempt}"
    if len(str(root)) >= 100:
        raise RuntimeError("short native path is unexpectedly long")
    root.mkdir(parents=True, exist_ok=True)
    return root


def archive_native(source: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(destination)
    relative = source.relative_to(SHORT_ROOT)
    physical_source = PHYSICAL_SHORT_ROOT / relative
    if not physical_source.exists():
        raise FileNotFoundError(physical_source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(physical_source), str(destination))


def candidate_path(native_root: Path, runner_id: str) -> Path | None:
    workflow = native_root / runner_id / "optminer_agent_workflow"
    for name in ("final_candidate.py", "candidate.py"):
        path = workflow / name
        if path.is_file():
            return path
    return None


def document_text(workflow: Path, result: dict[str, Any]) -> str | None:
    text_path = result.get("text_path")
    if isinstance(text_path, str) and text_path:
        direct = Path(text_path)
        if direct.is_file():
            return direct.read_text(encoding="utf-8", errors="replace")[:4000]
        named = workflow / "documents" / direct.name
        if named.is_file():
            return named.read_text(encoding="utf-8", errors="replace")[:4000]
    arxiv_id = str(result.get("arxiv_id") or "")
    safe_prefix = re.sub(r"[^A-Za-z0-9._-]", "_", arxiv_id)
    if safe_prefix:
        for path in sorted((workflow / "documents").glob(f"{safe_prefix}*.txt")):
            return path.read_text(encoding="utf-8", errors="replace")[:4000]
    abstract = result.get("abstract")
    return abstract[:4000] if isinstance(abstract, str) and abstract.strip() else None


def native_search(native_root: Path, runner_id: str) -> tuple[dict[str, Any], bool]:
    workflow = native_root / runner_id / "optminer_agent_workflow"
    path = workflow / "search_results.json"
    if not path.is_file():
        return {"queries": [], "pages": [], "search_count": 0, "pages_opened": 0, "backend": "arxiv_document"}, True
    rows = read_json(path)
    if not isinstance(rows, list):
        return {"queries": [], "pages": [], "search_count": 0, "pages_opened": 0, "backend": "arxiv_document"}, True
    queries: list[str] = []
    pages: list[dict[str, Any]] = []
    successful = False
    for search in rows:
        if not isinstance(search, dict):
            continue
        query = search.get("query")
        if isinstance(query, str) and query.strip():
            queries.append(query.strip())
        successful = successful or bool(search.get("ok"))
        for result in search.get("results") or []:
            if not isinstance(result, dict):
                continue
            url = result.get("url") or result.get("pdf_url")
            if not isinstance(url, str) or not url:
                continue
            original = document_text(workflow, result)
            pages.append(
                {
                    "title": str(result.get("title") or ""),
                    "url": url,
                    "publisher": "arXiv",
                    "original_text": [original] if original else [],
                    "extract_status": result.get("extract_status"),
                }
            )
    retrieval_failure = not queries or not successful or not pages
    return {
        "queries": queries,
        "pages": pages,
        "search_count": len(queries),
        "pages_opened": len(pages),
        "backend": "arxiv_document",
    }, retrieval_failure


def provider_failed(log_path: Path) -> bool:
    rows = read_jsonl(log_path) if log_path.is_file() else []
    return any(row.get("actual_model") != MODEL for row in rows)


def run_native_attempt(phase: str, task_id: str, attempt: int, packet_row: dict[str, Any], runner_id: str, attempt_dir: Path) -> dict[str, Any]:
    benchmark = attempt_dir / "benchmark.jsonl"
    write_jsonl(benchmark, [packet_row])
    server = None
    thread = None
    native_root = short_native_root(phase, task_id, attempt)
    try:
        server, thread, capability = proxy_context(attempt_dir, task_id)
        command = runner_command(attempt_dir, benchmark, runner_id, native_root, f"http://127.0.0.1:{server.server_address[1]}/v1")
        completed = subprocess.run(
            command,
            cwd=str(WORKFLOW_ROOT),
            env=child_environment(capability),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        (attempt_dir / "runner_stdout.txt").write_text(completed.stdout[-100000:], encoding="utf-8")
        (attempt_dir / "runner_stderr.txt").write_text(completed.stderr[-100000:], encoding="utf-8")
        archived = attempt_dir / "native_run"
        archive_native(native_root, archived)
        eval_path = attempt_dir / "native_eval.json"
        if completed.returncode != 0 or not eval_path.is_file():
            raise RuntimeError(f"native runner failed before evaluation: exit={completed.returncode}")
        payload = read_json(eval_path)
        rows = payload.get("rows") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or len(rows) != 1 or rows[0].get("expansion_id") != runner_id:
            raise RuntimeError("native evaluation row mismatch")
        return {"row": rows[0], "native_root": archived}
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)


def run_one(phase: str, task_id: str) -> dict[str, Any]:
    public = public_cases()[task_id]
    packet, mapping = inputs()
    runner_id = str(mapping[task_id]["runner_id"])
    task_dir = RUN_ROOT / phase / "optiminer" / task_id
    output_path = task_dir / "unified_output.json"
    if output_path.is_file():
        return read_json(output_path)
    task_dir.mkdir(parents=True, exist_ok=True)
    existing_attempts = sorted(path for path in task_dir.glob("attempt_*") if path.is_dir())
    if len(existing_attempts) >= 2:
        output = unified_output(
            method=METHOD,
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
    failure_detail = None
    search = None
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
        try:
            native = run_native_attempt(phase, task_id, attempt, packet[runner_id], runner_id, attempt_dir)
            native_row = native["row"]
            write_json(attempt_dir / "native_row.json", native_row)
            native_root = native["native_root"]
            search, retrieval_failure = native_search(native_root, runner_id)
            flags["retrieval_failure"] = retrieval_failure
            candidate = candidate_path(native_root, runner_id)
            execution: dict[str, Any]
            code: str | None = None
            if candidate is None:
                execution = {"status": "missing_candidate", "capture": None}
                flags["parse_failure"] = True
            else:
                code = candidate.read_text(encoding="utf-8")
                execution = execute_candidate(code, attempt_dir)
                if execution.get("status") != "success":
                    flags["parse_failure"] = True
            write_json(attempt_dir / "candidate_execution.json", execution)
            normalized = normalize_capture(output_schema_for(public), execution, generated_code=code)
            write_json(attempt_dir / "candidate_normalized.json", normalized)
            workflow = native_root / runner_id / "optminer_agent_workflow"
            trajectory = workflow / "trajectory.json"
            native_text = trajectory.read_text(encoding="utf-8", errors="replace") if trajectory.is_file() else None
            applicability, patch = explicit_applicability_and_patch(native_text)
            actions = normalized["actions"]
            objective = normalized["objective"]
            capture = execution.get("capture") if isinstance(execution, dict) else None
            solver_status = (
                "OPTIMAL"
                if execution.get("status") == "success" and isinstance(capture, dict) and capture.get("status") == 2
                else str(execution.get("status") or "EXECUTION_FAILURE").upper()
            )
            accounting = summarize_calls(attempt_dir / "api_calls.jsonl")
            if provider_failed(attempt_dir / "api_calls.jsonl"):
                flags["provider_failure"] = True
                failure_detail = str(native_row.get("error") or "native provider call failed")[:900]
            elif native_row.get("stage") == "unhandled_error":
                flags["runner_failure"] = True
                failure_detail = str(native_row.get("error") or "native runner failed")[:900]
            elif flags.get("parse_failure"):
                failure_detail = f"native candidate execution status: {execution.get('status')}"
            elif retrieval_failure:
                failure_detail = "native Arxiv retrieval produced no successful page set"
            native_artifacts = {
                "attempt_dir": str(attempt_dir),
                "native_entrypoint": str(ORIGINAL_RUNNER),
                "search_backend": "arxiv_document",
                "runner_id": runner_id,
                "action_mapping": str(normalized["action_mapping"]),
            }
            break
        except (ConfigurationViolation, GlobalStopError):
            raise
        except subprocess.TimeoutExpired as exc:
            (attempt_dir / "error_traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
            accounting = summarize_calls(attempt_dir / "api_calls.jsonl")
            if attempt == 1:
                continue
            flags["runner_failure"] = True
            failure_detail = f"native runner timeout after {exc.timeout} seconds"
        except (SyntaxError, ValueError) as exc:
            (attempt_dir / "error_traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
            accounting = summarize_calls(attempt_dir / "api_calls.jsonl")
            flags["parse_failure"] = True
            failure_detail = f"{type(exc).__name__}: {str(exc)[:900]}"
            break
        except Exception as exc:
            (attempt_dir / "error_traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
            accounting = summarize_calls(attempt_dir / "api_calls.jsonl")
            if attempt == 1 and accounting.get("calls") == 0:
                continue
            flags["runner_failure"] = True
            failure_detail = f"{type(exc).__name__}: {str(exc)[:900]}"
            break
    accounting["wall_total_seconds"] = time.perf_counter() - started
    output = unified_output(
        method=METHOD,
        phase=phase,
        public=public,
        search=search,
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
    output["native_search_backend"] = "arxiv_document"
    write_json(output_path, output)
    return output


def summary(phase: str, ids: list[str]) -> dict[str, Any]:
    outputs = []
    for task_id in ids:
        path = RUN_ROOT / phase / "optiminer" / task_id / "unified_output.json"
        if path.is_file():
            outputs.append(read_json(path))
    counts: dict[str, int] = {}
    for output in outputs:
        counts[output["status"]] = counts.get(output["status"], 0) + 1
    return {"method": METHOD, "phase": phase, "expected": len(ids), "completed": len(outputs), "status_counts": counts}


def run_worker(phase: str, task_id: str) -> tuple[str, int, str]:
    env = os.environ.copy()
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
    script = str(Path(__file__).resolve())
    bootstrap = "import runpy,sys;script=sys.argv.pop(1);sys.path.insert(0,script.rsplit('\\\\',1)[0]);sys.argv=[script,*sys.argv[1:]];runpy.run_path(script,run_name='__main__')"
    completed = subprocess.run(
        [str(PYTHON), "-I", "-c", bootstrap, script, "--phase", phase, "--worker-one", "--task-id", task_id],
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


def clean_empty_short_dirs(phase: str) -> None:
    phase_root = PHYSICAL_SHORT_ROOT / phase
    if phase_root.is_dir():
        for task_dir in sorted(phase_root.iterdir()):
            if task_dir.is_dir() and not any(task_dir.iterdir()):
                task_dir.rmdir()
        if not any(phase_root.iterdir()):
            phase_root.rmdir()
    if PHYSICAL_SHORT_ROOT.is_dir() and not any(PHYSICAL_SHORT_ROOT.iterdir()):
        PHYSICAL_SHORT_ROOT.rmdir()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run V1.5.1 native optiminer-training-free with Arxiv retrieval only.")
    parser.add_argument("--phase", choices=["smoke", "formal"], required=True)
    parser.add_argument("--task-ids", default="")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--worker-one", action="store_true")
    args = parser.parse_args()
    load_config()
    for path in (PYTHON, ORIGINAL_RUNNER, PACKET_PATH, MAPPING_PATH):
        if not path.exists():
            raise FileNotFoundError(path)
    alias_created = ensure_native_alias()
    try:
        if args.phase == "formal":
            if args.task_ids or args.task_id:
                raise SystemExit("Formal optiminer-training-free must run all fixed 240 cases; subsets are forbidden")
            validate_formal_gate()
        if args.worker_one:
            if not args.task_id:
                raise SystemExit("--worker-one requires --task-id")
            output = run_one(args.phase, args.task_id)
            print(json.dumps({"task_id": args.task_id, "status": output["status"]}, ensure_ascii=False))
            return 0
        ids = selected_ids(args.phase, args.task_ids)
        if not 1 <= args.workers <= 10:
            raise SystemExit("native optiminer workers must be between 1 and 10")
        error_log = RUN_ROOT / args.phase / "optiminer" / "runner_errors.log"
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(run_worker, args.phase, task_id): task_id for task_id in ids}
            for done, future in enumerate(as_completed(futures), start=1):
                task_id, returncode, output = future.result()
                snapshot = summary(args.phase, ids)
                write_json(RUN_ROOT / args.phase / "optiminer" / "summary.json", snapshot)
                print(json.dumps({"completed_processes": done, "task_id": task_id, "returncode": returncode, **snapshot}, ensure_ascii=False), flush=True)
                if returncode != 0:
                    error_log.parent.mkdir(parents=True, exist_ok=True)
                    with error_log.open("a", encoding="utf-8") as handle:
                        handle.write(f"[{task_id}] returncode={returncode}\n{output}\n")
        clean_empty_short_dirs(args.phase)
        final = summary(args.phase, ids)
        write_json(RUN_ROOT / args.phase / "optiminer" / "summary.json", final)
        print(json.dumps(final, ensure_ascii=False))
        return 0 if final["completed"] == len(ids) else 1
    finally:
        release_native_alias(alias_created)


if __name__ == "__main__":
    raise SystemExit(main())
