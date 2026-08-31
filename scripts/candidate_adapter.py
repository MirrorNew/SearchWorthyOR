from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import extract_json_object


PYTHON = Path(sys.executable).resolve()
EXECUTOR = Path(__file__).resolve().parent / "execute_candidate.py"

DENIED_NAMES = {
    "eval", "exec", "compile", "__import__", "globals", "locals", "getattr", "setattr",
    "delattr", "vars", "dir", "breakpoint", "input", "help", "__builtins__", "__loader__", "__spec__",
}
DENIED_MODULES = {
    "subprocess", "socket", "requests", "urllib", "http", "openai", "pathlib", "shutil",
    "ctypes", "multiprocessing", "threading", "asyncio", "winreg", "webbrowser",
}
ALLOWED_MODULES = {"gurobipy", "numpy", "itertools", "json", "os"}
SAFE_MODULE_ATTRIBUTES = {
    "gurobipy": {"Model", "GRB", "quicksum"},
    "itertools": {"combinations"},
    "json": {"load", "loads", "dumps"},
}
PURE_DYNAMIC_IMPORTS = {"itertools"}
UNUSED_ONLY_MODULES = {"os", "numpy"}
SAFE_FROM_IMPORTS = {
    "gurobipy": {"GRB", "Model", "quicksum"},
    "itertools": {"combinations"},
}
DENIED_ATTRIBUTES = {
    "system", "popen", "remove", "unlink", "rmdir", "removedirs", "rename", "renames",
    "replace", "walk", "listdir", "scandir", "environ", "getenv", "putenv", "spawnl",
    "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe",
    "fork", "kill", "startfile", "open", "read", "write", "writelines", "truncate",
    "Env", "getEnv", "readParams", "writeParams", "optimizeBatch", "modules",
}
DENIED_REFLECTION_PREFIXES = ("gi_", "cr_", "ag_", "f_", "tb_", "co_")


def _zero_literal(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and not isinstance(node.value, bool) and node.value == 0


def _safe_open_call(node: ast.Call) -> bool:
    if len(node.args) > 2 or any(isinstance(arg, ast.Starred) for arg in node.args):
        return False
    path: ast.AST | None = node.args[0] if node.args else None
    mode_node: ast.AST | None = node.args[1] if len(node.args) == 2 else None
    file_seen = path is not None
    mode_seen = mode_node is not None
    encoding_seen = False
    for keyword in node.keywords:
        if keyword.arg is None or keyword.arg not in {"file", "mode", "encoding"}:
            return False
        if keyword.arg == "file":
            if file_seen:
                return False
            file_seen = True
            path = keyword.value
        elif keyword.arg == "mode":
            if mode_seen:
                return False
            mode_seen = True
            mode_node = keyword.value
        else:
            if encoding_seen:
                return False
            encoding_seen = True
            if not isinstance(keyword.value, ast.Constant) or keyword.value.value not in {"utf-8", "utf8"}:
                return False
    if path is None:
        return False
    if not isinstance(path, ast.Constant) or path.value != "data.json":
        return False
    mode = "r" if mode_node is None else (
        mode_node.value if isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str) else None
    )
    if mode not in {"r", "rt", "rb"}:
        return False
    return not (mode == "rb" and encoding_seen)


def _safe_output_flag_store(node: ast.Attribute, parent: ast.AST | None) -> bool:
    if (
        node.attr != "OutputFlag"
        or not isinstance(node.value, ast.Attribute)
        or node.value.attr not in {"Params", "params"}
    ):
        return False
    if isinstance(parent, ast.Assign) and any(target is node for target in parent.targets):
        return _zero_literal(parent.value)
    if isinstance(parent, ast.AnnAssign) and parent.target is node and parent.value is not None:
        return _zero_literal(parent.value)
    return False


def _safe_set_param_call(node: ast.Attribute, parent: ast.AST | None) -> bool:
    return (
        node.attr == "setParam"
        and isinstance(parent, ast.Call)
        and parent.func is node
        and len(parent.args) == 2
        and not parent.keywords
        and isinstance(parent.args[0], ast.Constant)
        and parent.args[0].value == "OutputFlag"
        and _zero_literal(parent.args[1])
    )


def validate_candidate_code(code: str) -> None:
    if "\ufffd" in code:
        raise ValueError("generated code contains a replacement character")
    tree = ast.parse(code)
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    unused_only_aliases: set[str] = set()
    module_aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                import_name = alias.asname or alias.name
                prior = module_aliases.get(import_name)
                if prior is not None and prior != alias.name:
                    raise ValueError(f"ambiguous import alias: {import_name}")
                module_aliases[import_name] = alias.name
                if alias.name in UNUSED_ONLY_MODULES:
                    if alias.name == "os" and alias.asname is not None:
                        raise ValueError("unsafe os import form")
                    if alias.name == "numpy" and alias.asname not in {None, "np"}:
                        raise ValueError("unsafe numpy import form")
                    unused_only_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module in UNUSED_ONLY_MODULES:
                raise ValueError(f"unsafe from-import: {node.module}")

    optimize_calls = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in ALLOWED_MODULES or alias.name in DENIED_MODULES:
                    raise ValueError(f"unsafe import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = str(node.module or "")
            if node.level != 0 or module not in ALLOWED_MODULES or module in DENIED_MODULES:
                raise ValueError(f"unsafe from-import: {node.module}")
            safe_names = SAFE_FROM_IMPORTS.get(module)
            if safe_names is None or any(alias.name not in safe_names for alias in node.names):
                raise ValueError(f"unsafe {module} from-import")
        elif isinstance(node, ast.Name) and node.id in DENIED_NAMES:
            parent = parents.get(node)
            literal_module = (
                parent.args[0].value
                if (
                    node.id == "__import__"
                    and isinstance(parent, ast.Call)
                    and parent.func is node
                    and len(parent.args) == 1
                    and not parent.keywords
                    and isinstance(parent.args[0], ast.Constant)
                    and isinstance(parent.args[0].value, str)
                )
                else None
            )
            dynamic_attribute = parents.get(parent) if isinstance(parent, ast.Call) else None
            safe_literal_import = (
                literal_module in PURE_DYNAMIC_IMPORTS
                and isinstance(dynamic_attribute, ast.Attribute)
                and dynamic_attribute.value is parent
                and dynamic_attribute.attr in SAFE_MODULE_ATTRIBUTES[literal_module]
            )
            if not safe_literal_import:
                raise ValueError(f"unsafe name: {node.id}")
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in unused_only_aliases:
            raise ValueError(f"unsafe module use: {node.id}")
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in module_aliases:
            parent = parents.get(node)
            module = module_aliases[node.id]
            if not (
                isinstance(parent, ast.Attribute)
                and parent.value is node
                and parent.attr in SAFE_MODULE_ATTRIBUTES.get(module, set())
            ):
                raise ValueError(f"unsafe {module} module access")
        elif isinstance(node, ast.Name) and node.id == "open":
            parent = parents.get(node)
            if not (isinstance(parent, ast.Call) and parent.func is node and _safe_open_call(parent)):
                raise ValueError("unsafe open call")
        elif isinstance(node, ast.Attribute):
            if (
                node.attr.startswith("_")
                or node.attr.startswith(DENIED_REFLECTION_PREFIXES)
                or node.attr in DENIED_ATTRIBUTES
            ):
                raise ValueError(f"unsafe attribute: {node.attr}")
            parent = parents.get(node)
            if isinstance(node.ctx, ast.Store) and not _safe_output_flag_store(node, parent):
                raise ValueError(f"unsafe attribute store: {node.attr}")
            if node.attr in {"Params", "params"}:
                if not (
                    isinstance(parent, ast.Attribute)
                    and parent.value is node
                    and parent.attr == "OutputFlag"
                    and _safe_output_flag_store(parent, parents.get(parent))
                ):
                    raise ValueError("unsafe parameter access")
            if node.attr == "setParam" and not _safe_set_param_call(node, parent):
                raise ValueError("unsafe setParam call")
            if node.attr == "optimize":
                optimize_calls += 1
    if optimize_calls < 1:
        raise ValueError("generated code does not call optimize")


def _candidate_file_snapshot(task_dir: Path) -> tuple[set[str], dict[str, str | None]]:
    files = {
        path.relative_to(task_dir).as_posix()
        for path in task_dir.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    protected: dict[str, str | None] = {}
    for name in ("generated_code.py", "data.json"):
        path = task_dir / name
        if not path.exists() and not path.is_symlink():
            protected[name] = None
        elif path.is_symlink() or not path.is_file():
            protected[name] = "INVALID_FILE_TYPE"
        else:
            protected[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files, protected


def _apply_integrity_check(
    result: dict[str, Any],
    task_dir: Path,
    before: tuple[set[str], dict[str, str | None]],
) -> dict[str, Any]:
    after = _candidate_file_snapshot(task_dir)
    if after == before:
        return result
    result["status"] = "failed"
    result["capture"] = None
    result["integrity_violation"] = {
        "file_list_changed": before[0] != after[0],
        "protected_digest_changed": before[1] != after[1],
    }
    detail = "candidate execution changed task files or protected artifacts"
    result["stderr"] = (str(result.get("stderr") or "") + "\n" + detail).strip()
    return result


def execute_candidate(code: str, task_dir: Path, timeout_seconds: int = 90) -> dict[str, Any]:
    validate_candidate_code(code)
    code_path = task_dir / "generated_code.py"
    code_path.write_text(code, encoding="utf-8")
    before = _candidate_file_snapshot(task_dir)
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
            [str(PYTHON), "-X", "utf8", "-I", str(EXECUTOR), str(code_path)],
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
        return _apply_integrity_check({
            "status": "timeout",
            "returncode": None,
            "stdout": exc.stdout if isinstance(exc.stdout, str) else "",
            "stderr": exc.stderr if isinstance(exc.stderr, str) else "",
            "capture": None,
        }, task_dir, before)
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
    return _apply_integrity_check({
        "status": "success" if completed.returncode == 0 and isinstance(capture, dict) else "failed",
        "returncode": completed.returncode,
        "stdout": completed.stdout[-20000:],
        "stderr": completed.stderr[-20000:],
        "capture": capture,
    }, task_dir, before)


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


def normalize_solver_result_shell(
    action_specs: list[dict[str, Any]],
    capture: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]] | None, str]:
    """Map a baseline's solver variables to the public action order with strict shape/type guards."""
    if not capture or not isinstance(capture.get("variables"), list):
        return None, "solver_shell_no_model_capture"
    variables = capture["variables"]
    if len(variables) != len(action_specs) or not all(isinstance(row, dict) for row in variables):
        return None, "solver_shell_variable_count_mismatch"
    names = [row.get("name") for row in variables]
    if not all(isinstance(name, str) and name for name in names) or len(set(names)) != len(names):
        return None, "solver_shell_ambiguous_variable_names"
    expected_types = {"BINARY": "B", "INTEGER": "I", "CONTINUOUS": "C"}
    mapping: dict[str, Any] = {}
    for spec, row in zip(action_specs, variables):
        expected_type = expected_types.get(str(spec.get("type") or "").upper())
        if expected_type is None or row.get("type") != expected_type:
            return None, "solver_shell_variable_type_mismatch"
        mapping[str(spec["id"])] = row.get("value")
    actions = ordered_actions(action_specs, mapping)
    return (actions, "solver_capture_order_shell") if actions is not None else (None, "solver_shell_invalid_action_value")


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

    def add_literal(value: ast.AST | None) -> None:
        if isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value in accepted_units:
            found.add(value.value)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and identifier_key(target.id) == "objectiveunit" for target in targets):
                add_literal(node.value)
        elif isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg is not None and identifier_key(keyword.arg) == "objectiveunit":
                    add_literal(keyword.value)
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if (
                    isinstance(key, ast.Constant)
                    and isinstance(key.value, str)
                    and identifier_key(key.value) in {"unit", "objectiveunit"}
                ):
                    add_literal(value)
    return next(iter(found)) if len(found) == 1 else None


def normalize_capture(
    output_schema: dict[str, Any],
    execution: dict[str, Any],
    *,
    final_answer: str | None = None,
    generated_code: str | None = None,
    solver_result_shell: bool = False,
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
        if actions is None and solver_result_shell:
            actions, action_mapping = normalize_solver_result_shell(output_schema["actions"], capture)
    objective_value = capture.get("objective") if isinstance(capture, dict) else None
    if not isinstance(objective_value, (int, float)) or isinstance(objective_value, bool) or not math.isfinite(float(objective_value)):
        objective_value = None
    model_sense = capture.get("model_sense") if isinstance(capture, dict) else None
    direction = "min" if model_sense == 1 else "max" if model_sense == -1 else None
    objective_schema = output_schema.get("objective") if isinstance(output_schema.get("objective"), dict) else {}
    accepted_units = objective_schema.get("accepted_units") if isinstance(objective_schema.get("accepted_units"), dict) else {}
    unit = explicit_unit(stdout, accepted_units) or explicit_unit(final_answer or "", accepted_units)
    if unit is None:
        unit = source_unit(generated_code, accepted_units) or source_unit(final_answer, accepted_units)
    canonical_unit = objective_schema.get("canonical_unit")
    if unit is None and solver_result_shell and isinstance(canonical_unit, str) and canonical_unit in accepted_units:
        unit = canonical_unit
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
