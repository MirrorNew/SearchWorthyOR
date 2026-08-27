from __future__ import annotations

import ast
import json
import math
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from common import EXPERIMENT_ROOT, extract_json_object


PYTHON = Path(r"E:\my_evns\py312_torch28\python.exe")
EXECUTOR = Path(__file__).resolve().parent / "execute_candidate.py"

DENIED_NAMES = {
    "eval", "exec", "compile", "__import__", "globals", "locals", "getattr", "setattr",
    "delattr", "vars", "dir", "breakpoint", "input", "help",
}
DENIED_MODULES = {
    "subprocess", "socket", "requests", "urllib", "http", "openai", "pathlib", "shutil",
    "ctypes", "multiprocessing", "threading", "asyncio", "winreg", "webbrowser",
}
ALLOWED_MODULES = {"gurobipy", "numpy", "math", "itertools", "json", "collections", "os", "re"}
DENIED_ATTRIBUTES = {
    "system", "popen", "remove", "unlink", "rmdir", "removedirs", "rename", "renames",
    "replace", "walk", "listdir", "scandir", "environ", "getenv", "putenv", "spawnl",
    "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe",
    "fork", "kill", "startfile", "write", "writelines",
}


def validate_candidate_code(code: str) -> None:
    if "\ufffd" in code:
        raise ValueError("generated code contains a replacement character")
    tree = ast.parse(code)
    optimize_calls = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root not in ALLOWED_MODULES or root in DENIED_MODULES:
                    raise ValueError(f"unsafe import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = str(node.module or "").split(".", 1)[0]
            if root not in ALLOWED_MODULES or root in DENIED_MODULES:
                raise ValueError(f"unsafe from-import: {node.module}")
        elif isinstance(node, ast.Name) and node.id in DENIED_NAMES:
            raise ValueError(f"unsafe name: {node.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") or node.attr in DENIED_ATTRIBUTES:
                raise ValueError(f"unsafe attribute: {node.attr}")
            if node.attr == "optimize":
                optimize_calls += 1
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            if not node.args or not isinstance(node.args[0], ast.Constant):
                raise ValueError("only a literal data.json read is allowed")
            filename = str(node.args[0].value).replace("\\", "/").split("/")[-1]
            if filename != "data.json":
                raise ValueError("only a literal data.json read is allowed")
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and any(flag in str(node.args[1].value) for flag in "wax+"):
                raise ValueError("generated code cannot write files")
    if optimize_calls < 1:
        raise ValueError("generated code does not call optimize")


def execute_candidate(code: str, task_dir: Path, timeout_seconds: int = 90) -> dict[str, Any]:
    validate_candidate_code(code)
    code_path = task_dir / "generated_code.py"
    code_path.write_text(code, encoding="utf-8")
    env = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"),
        "TEMP": str(task_dir),
        "TMP": str(task_dir),
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "GRB_LICENSE_FILE": os.environ.get("GRB_LICENSE_FILE", ""),
    }
    try:
        completed = subprocess.run(
            [str(PYTHON), "-I", str(EXECUTOR), str(code_path)],
            cwd=str(task_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "returncode": None,
            "stdout": exc.stdout if isinstance(exc.stdout, str) else "",
            "stderr": exc.stderr if isinstance(exc.stderr, str) else "",
            "capture": None,
        }
    capture = None
    for line in reversed(completed.stdout.splitlines()):
        if not line.startswith("BASELINE_CAPTURE="):
            continue
        try:
            values = json.loads(line.split("=", 1)[1])
            if isinstance(values, list) and values:
                solved = [item for item in values if isinstance(item, dict) and item.get("objective") is not None]
                capture = solved[-1] if solved else values[-1]
        except Exception:
            capture = None
        break
    return {
        "status": "success" if completed.returncode == 0 and isinstance(capture, dict) else "failed",
        "returncode": completed.returncode,
        "stdout": completed.stdout[-20000:],
        "stderr": completed.stderr[-20000:],
        "capture": capture,
    }


def identifier_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def canonical_action_id(value: str, expected_ids: set[str]) -> str | None:
    if value in expected_ids:
        return value
    match = re.search(r"(?i)swor[^a-z0-9]*r0*(\d+)[^a-z0-9]*a0*(\d+)", value)
    if match:
        candidate = f"swor_r{int(match.group(1)):03d}_a{int(match.group(2)):02d}"
        if candidate in expected_ids:
            return candidate
    matches = [action_id for action_id in expected_ids if identifier_key(action_id) == identifier_key(value)]
    return matches[0] if len(matches) == 1 else None


def action_value(spec: dict[str, Any], value: Any) -> int | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        return None
    rounded = int(round(float(value)))
    if not math.isclose(float(value), rounded, rel_tol=0.0, abs_tol=1e-9):
        return None
    if str(spec.get("type") or "").upper() == "BINARY" and rounded not in {0, 1}:
        return None
    return rounded


def ordered_actions(action_specs: list[dict[str, Any]], mapping: dict[str, Any]) -> list[dict[str, Any]] | None:
    expected_ids = [str(spec["id"]) for spec in action_specs]
    if set(mapping) != set(expected_ids):
        return None
    result: list[dict[str, Any]] = []
    for spec in action_specs:
        value = action_value(spec, mapping[str(spec["id"])])
        if value is None:
            return None
        result.append({"id": str(spec["id"]), "value": value})
    return result


def selected_binary_actions(action_specs: list[dict[str, Any]], values: list[str]) -> list[dict[str, Any]] | None:
    if not action_specs or any(str(spec.get("type") or "").upper() != "BINARY" for spec in action_specs):
        return None
    expected_ids = {str(spec["id"]) for spec in action_specs}
    selected = [canonical_action_id(value, expected_ids) for value in values]
    if not selected or any(value is None for value in selected):
        return None
    chosen = set(selected)
    return [{"id": str(spec["id"]), "value": int(str(spec["id"]) in chosen)} for spec in action_specs]


def parse_action_candidates(value: Any, action_specs: list[dict[str, Any]], field: str = "") -> list[list[dict[str, Any]]]:
    expected_ids = {str(spec["id"]) for spec in action_specs}
    action_fields = {
        "action", "actions", "actionid", "actionids", "actionvalues", "decisions",
        "optimalaction", "optimalactions", "selectedaction", "selectedactions",
        "selectedactionid", "selectedactionids",
    }
    candidates: list[list[dict[str, Any]]] = []
    if isinstance(value, dict):
        direct: dict[str, Any] = {}
        for key, child in value.items():
            action_id = canonical_action_id(str(key), expected_ids)
            if action_id is not None:
                direct[action_id] = child
        complete = ordered_actions(action_specs, direct) if direct else None
        if complete is not None:
            candidates.append(complete)
        for key, child in value.items():
            child_field = identifier_key(str(key))
            if child_field in action_fields or isinstance(child, (dict, list)):
                candidates.extend(parse_action_candidates(child, action_specs, child_field))
        return candidates
    if isinstance(value, list):
        if field in action_fields and value and all(isinstance(item, str) for item in value):
            selected = selected_binary_actions(action_specs, value)
            if selected is not None:
                candidates.append(selected)
        rows: dict[str, Any] = {}
        for item in value:
            if not isinstance(item, dict):
                continue
            raw_id = item.get("id", item.get("action_id"))
            action_id = canonical_action_id(raw_id, expected_ids) if isinstance(raw_id, str) else None
            if action_id is not None and "value" in item:
                rows[action_id] = item["value"]
        complete = ordered_actions(action_specs, rows) if rows else None
        if complete is not None:
            candidates.append(complete)
        elif field in action_fields and rows and all(action_value({"type": "BINARY"}, item) == 1 for item in rows.values()):
            selected = selected_binary_actions(action_specs, list(rows))
            if selected is not None:
                candidates.append(selected)
        for child in value:
            if isinstance(child, (dict, list)):
                candidates.extend(parse_action_candidates(child, action_specs, field))
    return candidates


def line_objects(text: str) -> list[Any]:
    objects: list[Any] = []
    for line in text.splitlines():
        if "BASELINE_CAPTURE=" in line:
            continue
        for marker in ("{", "["):
            position = line.find(marker)
            if position < 0:
                continue
            fragment = line[position:].strip()
            for parser in (json.loads, ast.literal_eval):
                try:
                    objects.append(parser(fragment))
                    break
                except (ValueError, SyntaxError, json.JSONDecodeError):
                    pass
            break
    return objects


def explicit_actions_from_stdout(text: str, action_specs: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    candidates = [candidate for value in line_objects(text) for candidate in parse_action_candidates(value, action_specs)]
    labels = re.compile(r"(?i)\b(?:action_ids?|selected_actions?|selected_action_ids?|optimal_actions?)\s*[:=](.*)$")
    action_pattern = re.compile(r"(?i)swor[^\s,'\"\]\}]*r0*\d+[^\s,'\"\]\}]*a0*\d+")
    for line in text.splitlines():
        if "BASELINE_CAPTURE=" in line:
            continue
        match = labels.search(line)
        if not match:
            continue
        selected = selected_binary_actions(action_specs, action_pattern.findall(match.group(1)))
        if selected is not None:
            candidates.append(selected)
    unique = {tuple((row["id"], row["value"]) for row in candidate): candidate for candidate in candidates}
    return next(iter(unique.values())) if len(unique) == 1 else None


def normalize_actions(action_specs: list[dict[str, Any]], capture: dict[str, Any] | None) -> tuple[list[dict[str, Any]] | None, str]:
    """Accept only exact or reversibly normalized public action identifiers; never align by position."""
    if not capture or not isinstance(capture.get("variables"), list):
        return None, "no_model_capture"
    expected_ids = {str(action["id"]) for action in action_specs}
    by_id: dict[str, list[Any]] = {}
    for row in capture["variables"]:
        if not isinstance(row, dict) or not isinstance(row.get("name"), str):
            continue
        action_id = canonical_action_id(row["name"], expected_ids)
        if action_id is not None:
            by_id.setdefault(action_id, []).append(row.get("value"))
    if set(by_id) != expected_ids or any(len(values) != 1 for values in by_id.values()):
        return None, "missing_exact_identifier_variable"
    actions = ordered_actions(action_specs, {action_id: values[0] for action_id, values in by_id.items()})
    return (actions, "exact_identifier_normalization") if actions is not None else (None, "invalid_exact_action_value")


def normalize_actions_exact(action_specs: list[dict[str, Any]], capture: dict[str, Any] | None) -> tuple[list[dict[str, Any]] | None, str]:
    return normalize_actions(action_specs, capture)


def explicit_unit(text: str, accepted_units: dict[str, Any]) -> str | None:
    found: set[str] = set()
    for value in line_objects(text):
        stack = [value]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                for key, child in current.items():
                    if identifier_key(str(key)) in {"unit", "objectiveunit", "objectiveunits"} and isinstance(child, str) and child in accepted_units:
                        found.add(child)
                    elif isinstance(child, (dict, list)):
                        stack.append(child)
            elif isinstance(current, list):
                stack.extend(child for child in current if isinstance(child, (dict, list)))
    return next(iter(found)) if len(found) == 1 else None


def source_unit(source: str | None, accepted_units: dict[str, Any]) -> str | None:
    if not isinstance(source, str) or not source.strip():
        return None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if node.value in accepted_units:
            found.add(node.value)
        for match in re.finditer(r"(?i)objective_units?\s*[:=]\s*([^;,\n]+)", node.value):
            candidate = match.group(1).strip().strip("'\"{}[]()")
            if candidate in accepted_units:
                found.add(candidate)
    return next(iter(found)) if len(found) == 1 else None


def normalize_capture(
    output_schema: dict[str, Any],
    execution: dict[str, Any],
    *,
    final_answer: str | None = None,
    generated_code: str | None = None,
) -> dict[str, Any]:
    capture = execution.get("capture") if isinstance(execution, dict) else None
    if isinstance(capture, list) and len(capture) == 1 and isinstance(capture[0], dict):
        capture = capture[0]
    capture = capture if isinstance(capture, dict) else None
    stdout = execution.get("stdout") if isinstance(execution.get("stdout"), str) else ""
    actions = explicit_actions_from_stdout(stdout, output_schema["actions"])
    if actions is not None:
        action_mapping = "explicit_final_answer"
    else:
        actions, action_mapping = normalize_actions(output_schema["actions"], capture)
    objective_value = capture.get("objective") if isinstance(capture, dict) else None
    if not isinstance(objective_value, (int, float)) or isinstance(objective_value, bool) or not math.isfinite(float(objective_value)):
        objective_value = None
    model_sense = capture.get("model_sense") if isinstance(capture, dict) else None
    direction = "min" if model_sense == 1 else "max" if model_sense == -1 else None
    objective_schema = output_schema.get("objective") if isinstance(output_schema.get("objective"), dict) else {}
    accepted_units = objective_schema.get("accepted_units") if isinstance(objective_schema.get("accepted_units"), dict) else {}
    unit = explicit_unit(stdout, accepted_units)
    if unit is None:
        unit = source_unit(generated_code, accepted_units) or source_unit(final_answer, accepted_units)
    canonical_unit = objective_schema.get("canonical_unit")
    factor = accepted_units.get(unit) if unit is not None else None
    if objective_value is not None and isinstance(factor, (int, float)) and isinstance(canonical_unit, str):
        objective_value = float(objective_value) * float(factor)
        unit = canonical_unit
    return {
        "actions": actions,
        "action_mapping": action_mapping,
        "objective": {"value": objective_value, "direction": direction, "unit": unit} if objective_value is not None else None,
        "execution_status": execution.get("status"),
        "solver_status": capture.get("status") if isinstance(capture, dict) else None,
    }


def explicit_applicability_and_patch(text: str | None) -> tuple[dict[str, Any] | None, list[Any] | None]:
    if not isinstance(text, str) or not text.strip():
        return None, None
    try:
        value = extract_json_object(text)
    except ValueError:
        return None, None
    applicability = value.get("applicability")
    if not (
        isinstance(applicability, dict)
        and isinstance(applicability.get("applies"), bool)
        and isinstance(applicability.get("reason"), str)
    ):
        applicability = None
    patch = value.get("patch_elements")
    if not isinstance(patch, list):
        patch = None
    return applicability, patch
