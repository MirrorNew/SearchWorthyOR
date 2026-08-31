"""Launch Direct, Search-First, and SearchWorthy concurrently."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from common import (
    EXPERIMENT_ROOT,
    load_config,
    searchworthy_smoke_ids,
    validate_formal_gate,
    validate_smoke_launch_gate,
)


SCRIPT_ROOT = Path(__file__).resolve().parent


def commands(phase: str) -> dict[str, list[str]]:
    config = load_config()
    worker_key = f"{phase}_workers"
    methods = config["methods"]
    direct_workers = str(methods["Direct-v2 Base-Solve Gated Search"][worker_key])
    search_first_workers = str(methods["Search-First Gated Raw-NL"][worker_key])
    searchworthy_workers = str(methods["SearchWorthy"][worker_key])
    python = sys.executable
    result = {
        "direct": [python, "-X", "utf8", str(SCRIPT_ROOT / "run_direct.py"), "--phase", phase, "--workers", direct_workers],
        "search_first": [python, "-X", "utf8", str(SCRIPT_ROOT / "run_search_first.py"), "--phase", phase, "--workers", search_first_workers],
        "searchworthy": [
            python,
            "-X",
            "utf8",
            str(EXPERIMENT_ROOT / "searchworthy" / "run_searchworthy.py"),
            "--phase",
            phase,
            "--workers",
            searchworthy_workers,
        ],
    }
    if phase == "smoke":
        result["searchworthy"].extend(["--task-ids", ",".join(searchworthy_smoke_ids())])
    return result


def stop_running(processes: dict[str, subprocess.Popen[bytes]]) -> None:
    for process in processes.values():
        if process.poll() is None:
            process.terminate()
    for process in processes.values():
        if process.poll() is None:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the three public methods concurrently")
    parser.add_argument("--phase", choices=["smoke", "formal"], required=True)
    args = parser.parse_args()

    if args.phase == "smoke":
        validate_smoke_launch_gate()
    else:
        validate_formal_gate()

    env = os.environ.copy()
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
    processes: dict[str, subprocess.Popen[bytes]] = {}
    started = time.perf_counter()
    try:
        for slug, command in commands(args.phase).items():
            print(f"launch {slug}: {' '.join(command)}", flush=True)
            processes[slug] = subprocess.Popen(command, cwd=EXPERIMENT_ROOT, env=env)

        pending = set(processes)
        while pending:
            for slug in list(pending):
                return_code = processes[slug].poll()
                if return_code is None:
                    continue
                pending.remove(slug)
                if return_code != 0:
                    stop_running(processes)
                    raise RuntimeError(f"{slug} exited with code {return_code}")
            if pending:
                time.sleep(0.2)
    except BaseException:
        stop_running(processes)
        raise

    validator = [sys.executable, "-X", "utf8", str(SCRIPT_ROOT / "validate_outputs.py"), "--phase", args.phase]
    completed = subprocess.run(validator, cwd=EXPERIMENT_ROOT, env=env, check=False)
    elapsed = time.perf_counter() - started
    print(f"phase={args.phase} elapsed_seconds={elapsed:.3f} validation_exit={completed.returncode}", flush=True)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
