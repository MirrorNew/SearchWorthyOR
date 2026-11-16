"""Per-run free-variable adapter; leaves the frozen agent files untouched."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys


FREE_VARIABLE_NOTE = """
Input-format note: output_schema.actions is intentionally empty for these generic
optimization tasks. Declare every task decision variable and every auxiliary or
linearization variable needed by the mathematical model in the initial model,
using stable unique ASCII identifiers, the correct BINARY/INTEGER/CONTINUOUS type,
and explicit finite lower and upper bounds. Derive variables and bounds from the
task and supplied data only; do not add decisions or restrictions from assumptions.
Use the exact canonical objective unit from output_schema. Build an exact linear
mixed-integer model; linearize any nonlinear relationship exactly from the supplied
task. Keep the variable set, IDs, types, and bounds unchanged through later updates.
""".strip()


def _variables(document, fallback=None):
    if isinstance(document, dict):
        candidate = document.get("model", document)
        if isinstance(candidate, dict) and isinstance(candidate.get("variables"), list):
            return candidate["variables"]
    if isinstance(fallback, dict) and isinstance(fallback.get("variables"), list):
        return fallback["variables"]
    return []


def _dynamic_public(public, variables):
    dynamic = deepcopy(public)
    actions = []
    for variable in variables:
        if not isinstance(variable, dict):
            continue
        identifier, kind = variable.get("id"), variable.get("type")
        if not isinstance(identifier, str) or not identifier or kind not in {
            "BINARY", "INTEGER", "CONTINUOUS"
        }:
            continue
        actions.append({
            "id": identifier,
            "type": kind,
            "meaning": "Task decision or exact linearization variable",
        })
    dynamic["output_schema"]["actions"] = actions
    return dynamic


def install():
    """Patch only validator call sites for this subprocess."""
    agent_root = Path(__file__).resolve().parents[3] / "agent"
    if str(agent_root) not in sys.path:
        sys.path.insert(0, str(agent_root))
    from searchworthy import format_contract, table_loop
    from reevaluation import standard, standard_legacy

    original_compile = table_loop.compile_checked

    def free_compile(model, public, available):
        adapted = _dynamic_public(public, model.get("variables", []))
        return original_compile(model, adapted, available)

    original_normalize = format_contract.normalize_stage

    def free_normalize(document, purpose, public, model, table, available):
        variables = _variables(document, model if purpose != "PLAN_LITE" else None)
        adapted = _dynamic_public(public, variables)
        return original_normalize(document, purpose, adapted, model, table, available)

    original_repair = format_contract.check_repair
    original_legacy_compile = standard_legacy.compile_legacy_model

    def free_repair(original, repaired, paths, public):
        variables = _variables(original)
        adapted = _dynamic_public(public, variables)
        return original_repair(original, repaired, paths, adapted)

    def free_legacy_compile(model, schema):
        adapted = deepcopy(schema)
        adapted["actions"] = [
            {
                "id": row["id"],
                "type": row["type"],
                "meaning": "Task decision or exact linearization variable",
            }
            for row in model.get("variables", [])
            if isinstance(row, dict)
            and isinstance(row.get("id"), str)
            and row.get("type") in {"BINARY", "INTEGER", "CONTINUOUS"}
        ]
        return original_legacy_compile(model, adapted)

    table_loop.compile_checked = free_compile
    format_contract.normalize_stage = free_normalize
    format_contract.check_repair = free_repair
    standard_legacy.compile_legacy_model = free_legacy_compile
    if hasattr(standard, "compile_checked"):
        standard.compile_checked = free_compile
    if hasattr(standard, "normalize_stage"):
        standard.normalize_stage = free_normalize

    table_loop.PLAN = table_loop.PLAN + "\n\n" + FREE_VARIABLE_NOTE
    table_loop.UPDATE = table_loop.UPDATE + "\n\n" + FREE_VARIABLE_NOTE
    table_loop.FINAL_UPDATE = table_loop.FINAL_UPDATE + "\n\n" + FREE_VARIABLE_NOTE

    standard_legacy.BASE_MODEL_PROMPT = standard_legacy.BASE_MODEL_PROMPT.replace(
        "Gurobi", "COPT"
    ) + "\n\n" + FREE_VARIABLE_NOTE
    standard_legacy.FINAL_MODEL_PROMPT = standard_legacy.FINAL_MODEL_PROMPT.replace(
        "Gurobi", "COPT"
    ) + "\n\n" + FREE_VARIABLE_NOTE
    legacy_agent = getattr(standard_legacy, "LegacyStandardAgent", None)
    if legacy_agent is not None:
        legacy_agent.base_prompt = standard_legacy.BASE_MODEL_PROMPT
        legacy_agent.final_prompt = standard_legacy.FINAL_MODEL_PROMPT

    return {
        "version": "orlm_c3_free_variable_v1",
        "original_agents_modified": False,
        "public_actions_in_input": 0,
        "variables_declared_from_task": True,
        "updates_may_add_variables": False,
    }
