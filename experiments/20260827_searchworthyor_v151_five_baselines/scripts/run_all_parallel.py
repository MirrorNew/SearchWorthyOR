from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from common import EXPERIMENT_ROOT, GLOBAL_STOP_PATH, load_config, read_json, selected_ids, validate_formal_gate, write_json


PYTHON = Path(r"E:\my_evns\py312_torch28\python.exe")
SCRIPT_ROOT = Path(__file__).resolve().parent
RUN_ROOT = EXPERIMENT_ROOT / "runs"
ISOLATED_BOOTSTRAP = (
    "import runpy,sys;"
    "script=sys.argv.pop(1);"
    "sys.path.insert(0,script.rsplit('\\\\',1)[0]);"
    "sys.argv=[script,*sys.argv[1:]];"
    "runpy.run_path(script,run_name='__main__')"
)
METHODS = {
    "direct": [str(PYTHON), "-I", "-c", ISOLATED_BOOTSTRAP, str(SCRIPT_ROOT / "run_direct.py")],
    "coe": [str(PYTHON), "-I", "-c", ISOLATED_BOOTSTRAP, str(SCRIPT_ROOT / "run_local.py"), "--method", "coe"],
    "optimus": [str(PYTHON), "-I", "-c", ISOLATED_BOOTSTRAP, str(SCRIPT_ROOT / "run_local.py"), "--method", "optimus"],
    "optiminer": [str(PYTHON), "-I", "-c", ISOLATED_BOOTSTRAP, str(SCRIPT_ROOT / "run_optiminer.py")],
    "search_first": [str(PYTHON), "-I", "-c", ISOLATED_BOOTSTRAP, str(SCRIPT_ROOT / "run_search_first.py")],
}
METHOD_CONFIG_NAMES = {
    "direct": "Direct-v2 Base-Solve Gated Search",
    "coe": "CoE",
    "optimus": "OptiMUS",
    "optiminer": "optiminer-training-free",
    "search_first": "Search-First Gated Raw-NL",
}


def snapshot(phase: str, ids: list[str], methods: dict[str, list[str]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for method in methods:
        counts: dict[str, int] = {}
        completed = 0
        for task_id in ids:
            path = RUN_ROOT / phase / method / task_id / "unified_output.json"
            if not path.is_file():
                continue
            completed += 1
            status = str(read_json(path).get("status"))
            counts[status] = counts.get(status, 0) + 1
        result[method] = {"completed": completed, "expected": len(ids), "status_counts": counts}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch all five V1.5.1 baselines concurrently.")
    parser.add_argument("--phase", choices=["smoke", "formal"], required=True)
    args = parser.parse_args()
    config = load_config()
    if args.phase == "formal":
        validate_formal_gate()
    active_methods = METHODS
    worker_field = "smoke_workers" if args.phase == "smoke" else "formal_workers"
    worker_counts = {
        method: int(config["methods"][METHOD_CONFIG_NAMES[method]][worker_field]) for method in active_methods
    }
    expected_total = 5 if args.phase == "smoke" else 15
    expected_each = 1 if args.phase == "smoke" else 3
    if any(value != expected_each for value in worker_counts.values()) or sum(worker_counts.values()) != expected_total:
        raise SystemExit(f"{args.phase} worker configuration changed")
    if int(config["parallelism"][f"{args.phase}_total_workers"]) != expected_total:
        raise SystemExit(f"{args.phase} total worker contract changed")
    ids = selected_ids(args.phase)
    orchestration_dir = RUN_ROOT / args.phase / "orchestration"
    orchestration_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
    processes: dict[str, tuple[subprocess.Popen[str], Any]] = {}
    for method, prefix in active_methods.items():
        log_handle = (orchestration_dir / f"{method}.log").open("a", encoding="utf-8", newline="\n")
        command = [*prefix, "--phase", args.phase, "--workers", str(worker_counts[method])]
        process = subprocess.Popen(
            command,
            cwd=str(EXPERIMENT_ROOT),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        processes[method] = (process, log_handle)
    started = time.perf_counter()
    returncodes: dict[str, int] = {}
    try:
        while len(returncodes) < len(processes):
            if GLOBAL_STOP_PATH.is_file():
                for process, _ in processes.values():
                    if process.poll() is None:
                        process.terminate()
                raise RuntimeError(f"global stop activated: {read_json(GLOBAL_STOP_PATH)}")
            for method, (process, _) in processes.items():
                code = process.poll()
                if code is not None:
                    returncodes[method] = code
            print(json.dumps({"phase": args.phase, "elapsed_seconds": round(time.perf_counter() - started, 1), "methods": snapshot(args.phase, ids, active_methods), "returncodes": returncodes}, ensure_ascii=False), flush=True)
            if len(returncodes) < len(processes):
                time.sleep(15)
    finally:
        for process, handle in processes.values():
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=30)
            handle.close()
    final = {
        "schema_version": "searchworthyor.v151.parallel_run_summary.v1",
        "phase": args.phase,
        "wall_seconds": time.perf_counter() - started,
        "worker_counts": worker_counts,
        "returncodes": returncodes,
        "methods": snapshot(args.phase, ids, active_methods),
    }
    write_json(orchestration_dir / "summary.json", final)
    print(json.dumps(final, ensure_ascii=False, indent=2))
    complete = all(row["completed"] == len(ids) for row in final["methods"].values())
    return 0 if complete and all(code == 0 for code in returncodes.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
