from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ALLOWED_IMPORT_ROOTS = {"__future__", "gurobipy", "json", "math", "pathlib"}
FORBIDDEN_CALLS = {
    "eval",
    "exec",
    "compile",
    "open",
    "__import__",
    "input",
}
FORBIDDEN_METHOD_CALLS = {
    "glob",
    "iterdir",
    "open",
    "read_bytes",
    "read_text",
    "rglob",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_last_json_object(text: str) -> dict[str, Any]:
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        object_start = stripped.find("{")
        if object_start < 0:
            continue
        try:
            value = json.loads(stripped[object_start:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("No JSON object found in stdout.")


def normalize_action(value: Any) -> list[str]:
    if isinstance(value, dict):
        return sorted(
            str(key).upper()
            for key, item in value.items()
            if int(round(float(item))) == 1
        )
    if isinstance(value, list):
        if all(isinstance(item, str) for item in value):
            return sorted(str(item).upper() for item in value)
        return [
            chr(ord("A") + index)
            for index, item in enumerate(value)
            if int(round(float(item))) == 1
        ]
    raise TypeError(f"Unsupported projected action format: {type(value).__name__}")


def static_code_check(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(path))
    imports = []
    forbidden = []
    forbidden_methods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_CALLS:
                forbidden.append(node.func.id)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in FORBIDDEN_METHOD_CALLS:
                forbidden_methods.append(node.func.attr)
    disallowed_imports = sorted(
        {
            name
            for name in imports
            if name.split(".", 1)[0] not in ALLOWED_IMPORT_ROOTS
        }
    )
    return {
        "imports": sorted(set(imports)),
        "disallowed_imports": disallowed_imports,
        "forbidden_calls": sorted(set(forbidden)),
        "forbidden_method_calls": sorted(set(forbidden_methods)),
        "passed": not disallowed_imports and not forbidden and not forbidden_methods,
    }


def replay_model(
    model_path: Path,
    replay_dir: Path,
    python_executable: str,
    expected_result: dict[str, Any],
) -> dict[str, Any]:
    replay_dir.mkdir(parents=True, exist_ok=True)
    replay_model_path = replay_dir / model_path.name
    shutil.copy2(model_path, replay_model_path)
    completed = subprocess.run(
        [python_executable, str(replay_model_path.resolve())],
        cwd=replay_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    stdout_path = replay_dir / "replay.stdout.txt"
    stderr_path = replay_dir / "replay.stderr.txt"
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    try:
        replayed = parse_last_json_object(completed.stdout)
    except ValueError:
        replayed = {}
    expected_status = expected_result.get(
        "solver_status", expected_result.get("status")
    )
    replay_status = replayed.get("status")
    status_match = replay_status == expected_status
    objective_match = abs(
        float(replayed.get("objective")) - float(expected_result.get("objective"))
    ) <= 1e-6
    replay_action = replayed.get(
        "projected_action", replayed.get("selected")
    )
    expected_action = expected_result.get(
        "projected_action", expected_result.get("selected")
    )
    action_match = normalize_action(replay_action) == normalize_action(
        expected_action
    )
    passed = (
        completed.returncode == 0
        and not completed.stderr.strip()
        and status_match
        and objective_match
        and action_match
    )
    return {
        "passed": passed,
        "returncode": completed.returncode,
        "stderr_empty": not completed.stderr.strip(),
        "status_match": status_match,
        "objective_match": objective_match,
        "action_match": action_match,
        "model_sha256": sha256(replay_model_path),
        "stdout_sha256": sha256(stdout_path),
        "stderr_sha256": sha256(stderr_path),
    }


def verify_task(
    task_dir: Path,
    replay_root: Path | None,
    python_executable: str,
) -> dict[str, Any]:
    result_path = task_dir / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8-sig"))
    stdout_path = task_dir / "execution.stdout.txt"
    stderr_path = task_dir / "execution.stderr.txt"
    if not stdout_path.exists() or not stderr_path.exists():
        successful_attempts = [
            item
            for item in result.get("execution_record", [])
            if item.get("ok")
        ]
        if not successful_attempts:
            raise FileNotFoundError(f"No successful execution logs in {task_dir}")
        latest = successful_attempts[-1]
        stdout_path = task_dir / latest["stdout_log"]
        stderr_path = task_dir / latest["stderr_log"]
    stdout = stdout_path.read_text(encoding="utf-8-sig")
    stderr = stderr_path.read_text(encoding="utf-8-sig")
    executed = parse_last_json_object(stdout)
    model_candidates = sorted(task_dir.glob("model*.py"))
    if not model_candidates:
        raise FileNotFoundError(f"No model*.py in {task_dir}")
    code_checks = [static_code_check(path) for path in model_candidates]
    independent_replay = (
        replay_model(
            model_candidates[0],
            replay_root / task_dir.name,
            python_executable,
            result,
        )
        if replay_root is not None
        else None
    )

    task_id = result.get("task_id", result.get("id", task_dir.name))
    expected_status = result.get("solver_status", result.get("status"))
    status_match = executed.get("status") == expected_status
    objective_match = abs(
        float(executed.get("objective")) - float(result.get("objective"))
    ) <= 1e-6
    executed_action = executed.get("projected_action", executed.get("selected"))
    result_action = result.get("projected_action", result.get("selected"))
    action_match = normalize_action(executed_action) == normalize_action(result_action)
    stderr_empty = not stderr.strip()
    passed = (
        status_match
        and objective_match
        and action_match
        and stderr_empty
        and all(check["passed"] for check in code_checks)
        and (
            independent_replay is None
            or independent_replay["passed"]
        )
    )
    return {
        "task_id": task_id,
        "passed": passed,
        "status_match": status_match,
        "objective_match": objective_match,
        "action_match": action_match,
        "stderr_empty": stderr_empty,
        "independent_replay": independent_replay,
        "models": [
            {
                "path": str(path),
                "sha256": sha256(path),
                "static_check": check,
            }
            for path, check in zip(model_candidates, code_checks, strict=True)
        ],
        "stdout_sha256": sha256(stdout_path),
        "stderr_sha256": sha256(stderr_path),
        "result_sha256": sha256(result_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--replay-root", type=Path)
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()

    rows = [
        verify_task(path, args.replay_root, args.python)
        for path in sorted(args.run_root.glob("SWOR*"))
    ]
    output = {
        "run_root": str(args.run_root),
        "tasks": len(rows),
        "passed": all(row["passed"] for row in rows),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"tasks": len(rows), "passed": output["passed"]}, ensure_ascii=False))
    return 0 if output["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
