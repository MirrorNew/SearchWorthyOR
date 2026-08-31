"""Canonical linear-OR IR validation, solving, impact probes, and Patch re-solve.

The solver, not the LLM, owns feasibility and decision/value comparisons.
Current impact probes are intentionally narrow: only program-verifiable bounded
counterfactuals may influence the search trigger.
"""

from __future__ import annotations

import copy
import itertools
import math
from typing import Any

import gurobipy as gp
from gurobipy import GRB

from .contracts import (
    DecisionCompleteORState,
    GapState,
    PatchBundle,
    PotentialEffect,
    SolveCapture,
    StateUpdate,
)
from .state import apply_state_update


class IRValidationError(ValueError):
    pass


class SolverError(RuntimeError):
    pass


ValidatedIR = dict[str, Any]
TARGET_PREFIXES = {"variable", "parameter", "constraint", "objective"}
VAR_TYPES = {"BINARY", "INTEGER", "CONTINUOUS"}
SENSES = {"<=", "==", ">="}


def _finite(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise IRValidationError(f"{label} must be a finite number")
    number = float(value)
    if abs(number) > 1e12:
        raise IRValidationError(f"{label} exceeds numeric safety bounds")
    return number


def split_target(target: str) -> tuple[str, str]:
    if not isinstance(target, str) or "." not in target:
        raise IRValidationError("target must use family.slot form")
    family, slot = target.split(".", 1)
    if family not in TARGET_PREFIXES or not slot.strip():
        raise IRValidationError("target family or slot is invalid")
    return family, slot.strip()


def target_exists_or_legal_slot(model_ir: ValidatedIR, target: str) -> bool:
    family, slot = split_target(target)
    variable_ids = {row["id"] for row in model_ir["variables"]}
    constraint_names = {row["name"] for row in model_ir["constraints"]}
    if family == "variable":
        return slot in variable_ids
    if family == "objective":
        return slot in variable_ids or slot == "constant"
    if family == "constraint":
        return bool(slot)  # a named, not-yet-existing constraint is a legal insertion slot
    return bool(slot)  # parameters may be introduced, but only an effective re-solve can close the gap


def target_value(model_ir: ValidatedIR, target: str) -> Any:
    family, slot = split_target(target)
    if family == "variable":
        row = next((item for item in model_ir["variables"] if item["id"] == slot), None)
        return {"lb": row["lb"], "ub": row["ub"]} if row else None
    if family == "constraint":
        return copy.deepcopy(next((item for item in model_ir["constraints"] if item["name"] == slot), None))
    if family == "objective":
        if slot == "constant":
            return model_ir["objective"]["constant"]
        term = next((item for item in model_ir["objective"]["terms"] if item["var"] == slot), None)
        return term["coef"] if term else None
    return copy.deepcopy(model_ir.get("parameters", {}).get(slot))


def validate_ir(model_ir: dict[str, Any], output_schema: dict[str, Any] | None = None) -> ValidatedIR:
    if not isinstance(model_ir, dict) or not {"variables", "constraints", "objective"}.issubset(model_ir):
        raise IRValidationError("model_ir requires variables, constraints and objective")
    if set(model_ir) - {"variables", "constraints", "objective", "parameters"}:
        raise IRValidationError("model_ir contains unsupported top-level fields")

    expected_specs = output_schema.get("actions") if isinstance(output_schema, dict) else None
    expected_ids = [str(row["id"]) for row in expected_specs] if isinstance(expected_specs, list) else None
    rows = model_ir["variables"]
    if not isinstance(rows, list) or not rows:
        raise IRValidationError("model_ir variables must be non-empty")
    if expected_ids is not None and len(rows) != len(expected_ids):
        raise IRValidationError("model_ir must declare every public action exactly once")
    variables: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"id", "type", "lb", "ub"}:
            raise IRValidationError("variable rows must contain id, type, lb and ub")
        identifier = str(row["id"])
        if not identifier or identifier in seen_ids:
            raise IRValidationError("variable IDs must be non-empty and unique")
        if expected_ids is not None and identifier != expected_ids[index]:
            raise IRValidationError("model_ir variable order/identity differs from public output_schema")
        variable_type = str(row["type"]).upper()
        if variable_type not in VAR_TYPES:
            raise IRValidationError("unsupported variable type")
        if expected_specs is not None:
            expected_type = str(expected_specs[index].get("type") or "").upper()
            if expected_type and variable_type != expected_type:
                raise IRValidationError("variable type differs from public output_schema")
        lower, upper = _finite(row["lb"], "variable lower bound"), _finite(row["ub"], "variable upper bound")
        if lower > upper or (variable_type == "BINARY" and (lower not in {0.0, 1.0} or upper not in {0.0, 1.0})):
            raise IRValidationError("variable bounds are invalid")
        variables.append({"id": identifier, "type": variable_type, "lb": lower, "ub": upper})
        seen_ids.add(identifier)

    constraints_value = model_ir["constraints"]
    if not isinstance(constraints_value, list) or len(constraints_value) > 200:
        raise IRValidationError("constraints must be a list of at most 200 rows")
    constraints: list[dict[str, Any]] = []
    names: set[str] = set()
    for row in constraints_value:
        if not isinstance(row, dict) or set(row) != {"name", "terms", "sense", "rhs"}:
            raise IRValidationError("constraint rows have an invalid contract")
        name = str(row["name"]).strip()
        if not name or name in names or row["sense"] not in SENSES:
            raise IRValidationError("constraint name/sense is invalid")
        terms = row["terms"]
        if not isinstance(terms, list) or not terms:
            raise IRValidationError("constraint terms must be non-empty")
        normalized_terms: list[dict[str, Any]] = []
        seen_terms: set[str] = set()
        for term in terms:
            if not isinstance(term, dict) or set(term) != {"var", "coef"}:
                raise IRValidationError("constraint term has an invalid contract")
            variable = str(term["var"])
            if variable not in seen_ids or variable in seen_terms:
                raise IRValidationError("constraint term variable is unknown or duplicated")
            normalized_terms.append({"var": variable, "coef": _finite(term["coef"], "constraint coefficient")})
            seen_terms.add(variable)
        constraints.append(
            {"name": name, "terms": normalized_terms, "sense": row["sense"], "rhs": _finite(row["rhs"], "constraint rhs")}
        )
        names.add(name)

    objective = model_ir["objective"]
    if not isinstance(objective, dict) or set(objective) != {"direction", "terms", "constant", "unit"}:
        raise IRValidationError("objective has an invalid contract")
    if objective["direction"] not in {"min", "max"}:
        raise IRValidationError("objective direction must be min or max")
    unit = objective["unit"]
    if not isinstance(unit, str) or not unit:
        raise IRValidationError("objective unit must be non-empty")
    if output_schema is not None:
        accepted = output_schema.get("objective", {}).get("accepted_units")
        if not isinstance(accepted, dict) or unit not in accepted:
            raise IRValidationError("objective unit is not accepted by the public schema")
    terms = objective["terms"]
    if not isinstance(terms, list):
        raise IRValidationError("objective terms must be a list")
    objective_terms: list[dict[str, Any]] = []
    seen_objective: set[str] = set()
    for term in terms:
        if not isinstance(term, dict) or set(term) != {"var", "coef"}:
            raise IRValidationError("objective term has an invalid contract")
        variable = str(term["var"])
        if variable not in seen_ids or variable in seen_objective:
            raise IRValidationError("objective term variable is unknown or duplicated")
        objective_terms.append({"var": variable, "coef": _finite(term["coef"], "objective coefficient")})
        seen_objective.add(variable)

    parameters_value = model_ir.get("parameters", {})
    if not isinstance(parameters_value, dict) or any(not isinstance(key, str) or not key for key in parameters_value):
        raise IRValidationError("parameters must be a string-keyed object")
    parameters = {key: _finite(value, f"parameter {key}") for key, value in parameters_value.items()}
    return {
        "variables": variables,
        "constraints": constraints,
        "objective": {
            "direction": objective["direction"],
            "terms": objective_terms,
            "constant": _finite(objective["constant"], "objective constant"),
            "unit": unit,
        },
        "parameters": parameters,
    }


def compact_binary_upper_bound_constraints(model_ir: dict[str, Any]) -> ValidatedIR:
    """Replace small positive-binary upper bounds by exact minimal no-goods.

    This keeps the feasible set unchanged.  It is intentionally bounded to
    rows with at most 12 terms and is used only when the resulting IR is
    strictly smaller than the validated input.
    """
    validated = validate_ir(model_ir)
    variable_rows = {row["id"]: row for row in validated["variables"]}
    kept: list[dict[str, Any]] = []
    forbidden_sets: set[frozenset[str]] = set()

    for row in validated["constraints"]:
        terms = row["terms"]
        eligible = (
            row["sense"] == "<="
            and row["rhs"] >= 0
            and len(terms) <= 12
            and all(term["coef"] > 0 for term in terms)
            and all(
                variable_rows[term["var"]]["type"] == "BINARY"
                and variable_rows[term["var"]]["lb"] == 0
                and variable_rows[term["var"]]["ub"] == 1
                for term in terms
            )
        )
        if not eligible:
            kept.append(copy.deepcopy(row))
            continue

        coefficients = {term["var"]: term["coef"] for term in terms}
        identifiers = sorted(coefficients)
        row_forbidden: set[frozenset[str]] = set()
        for size in range(1, len(identifiers) + 1):
            for subset in itertools.combinations(identifiers, size):
                total = sum(coefficients[identifier] for identifier in subset)
                if total <= row["rhs"]:
                    continue
                if all(total - coefficients[identifier] <= row["rhs"] for identifier in subset):
                    row_forbidden.add(frozenset(subset))
        forbidden_sets.update(row_forbidden)

    minimal_forbidden = [
        subset
        for subset in sorted(forbidden_sets, key=lambda value: (len(value), sorted(value)))
        if not any(other < subset for other in forbidden_sets)
    ]
    existing_names = {row["name"] for row in kept}
    compacted = list(kept)
    for index, subset in enumerate(minimal_forbidden, start=1):
        name = f"sw_nogood_{index:04d}"
        while name in existing_names:
            index += 1
            name = f"sw_nogood_{index:04d}"
        existing_names.add(name)
        compacted.append(
            {
                "name": name,
                "terms": [{"var": identifier, "coef": 1.0} for identifier in sorted(subset)],
                "sense": "<=",
                "rhs": float(len(subset) - 1),
            }
        )

    if len(compacted) >= len(validated["constraints"]) or len(compacted) > 200:
        return validated
    result = copy.deepcopy(validated)
    result["constraints"] = compacted
    return validate_ir(result)


def compile_and_solve(model_ir: ValidatedIR, output_schema: dict[str, Any] | None = None) -> SolveCapture:
    try:
        model = gp.Model("searchworthy_ir")
        model.Params.OutputFlag = 0
        model.Params.Threads = 1
        model.Params.TimeLimit = 90
        model.Params.PoolSearchMode = 2
        model.Params.PoolSolutions = 128
        model.Params.PoolGap = 0
        variables: dict[str, gp.Var] = {}
        for row in model_ir["variables"]:
            vtype = {"BINARY": GRB.BINARY, "INTEGER": GRB.INTEGER, "CONTINUOUS": GRB.CONTINUOUS}[row["type"]]
            variables[row["id"]] = model.addVar(lb=row["lb"], ub=row["ub"], vtype=vtype, name=row["id"])
        model.update()
        for row in model_ir["constraints"]:
            expression = gp.quicksum(term["coef"] * variables[term["var"]] for term in row["terms"])
            if row["sense"] == "<=":
                model.addConstr(expression <= row["rhs"], name=row["name"])
            elif row["sense"] == ">=":
                model.addConstr(expression >= row["rhs"], name=row["name"])
            else:
                model.addConstr(expression == row["rhs"], name=row["name"])
        objective = model_ir["objective"]
        expression = gp.quicksum(term["coef"] * variables[term["var"]] for term in objective["terms"]) + objective["constant"]
        model.setObjective(expression, GRB.MINIMIZE if objective["direction"] == "min" else GRB.MAXIMIZE)
        model.optimize()
    except gp.GurobiError as exc:
        raise SolverError(str(exc)) from exc

    diagnostic = {
        "variable_count": len(model_ir["variables"]),
        "constraint_count": len(model_ir["constraints"]),
    }
    if model.Status != GRB.OPTIMAL:
        return SolveCapture(
            status="INFEASIBLE" if model.Status in {GRB.INFEASIBLE, GRB.INF_OR_UNBD} else "SOLVER_FAILURE",
            feasible=False,
            actions=None,
            objective=None,
            solver_status=int(model.Status),
            diagnostic=diagnostic,
        )

    action_order = (
        [str(row["id"]) for row in output_schema["actions"]]
        if isinstance(output_schema, dict) and isinstance(output_schema.get("actions"), list)
        else [row["id"] for row in model_ir["variables"]]
    )
    action_sets: set[tuple[int, ...]] = set()
    for solution_number in range(int(model.SolCount)):
        model.Params.SolutionNumber = solution_number
        values: list[int] = []
        for identifier in action_order:
            value = float(variables[identifier].Xn)
            rounded = int(round(value))
            if not math.isclose(value, rounded, rel_tol=0.0, abs_tol=1e-6):
                raise SolverError("public action variable is non-integral")
            values.append(rounded)
        action_sets.add(tuple(values))
    if not action_sets:
        raise SolverError("solver returned no optimal action solution")
    canonical_actions = min(action_sets)
    actions = [{"id": identifier, "value": value} for identifier, value in zip(action_order, canonical_actions)]
    diagnostic["optimal_action_sets"] = [list(values) for values in sorted(action_sets)]
    diagnostic["optimal_action_sets_truncated"] = int(model.SolCount) >= 128

    unit, value = objective["unit"], float(model.ObjVal)
    if output_schema is not None:
        accepted = output_schema["objective"]["accepted_units"]
        value *= _finite(accepted[unit], "unit conversion factor")
        unit = output_schema["objective"]["canonical_unit"]
    return SolveCapture(
        status="OPTIMAL",
        feasible=True,
        actions=actions,
        objective={"sense": objective["direction"], "value": value, "unit": unit},
        solver_status=int(model.Status),
        diagnostic=diagnostic,
    )


def solve_initial(model_ir: dict[str, Any], output_schema: dict[str, Any] | None = None) -> tuple[ValidatedIR, SolveCapture]:
    validated = validate_ir(model_ir, output_schema)
    return validated, compile_and_solve(validated, output_schema)


def compare_solves(base: SolveCapture, candidate: SolveCapture) -> tuple[PotentialEffect, dict[str, Any]]:
    if base.feasible != candidate.feasible:
        effect = PotentialEffect.FEASIBILITY_CHANGE
    elif not base.feasible and not candidate.feasible:
        effect = PotentialEffect.NO_EFFECT
    else:
        base_sets = base.diagnostic.get("optimal_action_sets")
        candidate_sets = candidate.diagnostic.get("optimal_action_sets")
        pools_complete = (
            isinstance(base_sets, list)
            and isinstance(candidate_sets, list)
            and base.diagnostic.get("optimal_action_sets_truncated") is False
            and candidate.diagnostic.get("optimal_action_sets_truncated") is False
        )
        if pools_complete and base_sets != candidate_sets:
            effect = PotentialEffect.DECISION_CHANGE
        elif not pools_complete:
            effect = PotentialEffect.UNKNOWN
        else:
            base_value = base.objective.get("value") if isinstance(base.objective, dict) else None
            candidate_value = candidate.objective.get("value") if isinstance(candidate.objective, dict) else None
            changed = (
                isinstance(base_value, (int, float))
                and isinstance(candidate_value, (int, float))
                and not math.isclose(float(base_value), float(candidate_value), rel_tol=1e-9, abs_tol=1e-8)
            )
            effect = PotentialEffect.VALUE_CHANGE if changed else PotentialEffect.NO_EFFECT
    return effect, {
        "effect": effect.value,
        "base_feasible": base.feasible,
        "candidate_feasible": candidate.feasible,
        "base_actions": base.actions,
        "candidate_actions": candidate.actions,
        "base_objective": base.objective,
        "candidate_objective": candidate.objective,
    }


def _apply_hypothetical_variant(current_ir: ValidatedIR, variant: dict[str, Any], expected_target: str) -> ValidatedIR:
    if not {"target", "operation", "value", "range_basis"}.issubset(variant) or set(variant) - {
        "target", "operation", "value", "range_basis", "basis_quote"
    }:
        raise IRValidationError("hypothetical variant has an invalid contract")
    if variant["target"] != expected_target or variant["operation"] not in {"SET", "ADD", "REMOVE"}:
        raise IRValidationError("hypothetical variant target/operation is invalid")
    if variant["range_basis"] not in {"PROMPT", "MODEL_BOUNDARY", "PREREGISTERED_RULE"}:
        raise IRValidationError("hypothetical variant lacks a registered range basis")
    patched = copy.deepcopy(current_ir)
    family, slot = split_target(expected_target)
    operation, value = variant["operation"], copy.deepcopy(variant["value"])
    if family == "variable" and operation == "SET":
        row = next((item for item in patched["variables"] if item["id"] == slot), None)
        if row is None or not isinstance(value, dict) or set(value) != {"lb", "ub"}:
            raise IRValidationError("variable probe value is invalid")
        row["lb"], row["ub"] = value["lb"], value["ub"]
    elif family == "objective" and operation == "SET":
        if slot == "constant":
            patched["objective"]["constant"] = value
        else:
            term = next((item for item in patched["objective"]["terms"] if item["var"] == slot), None)
            if term is None:
                patched["objective"]["terms"].append({"var": slot, "coef": value})
            else:
                term["coef"] = value
    elif family == "constraint":
        index = next((i for i, item in enumerate(patched["constraints"]) if item["name"] == slot), None)
        if operation in {"SET", "ADD"}:
            if not isinstance(value, dict):
                raise IRValidationError("constraint probe value must be an object")
            value["name"] = slot
            if index is None:
                patched["constraints"].append(value)
            else:
                patched["constraints"][index] = value
        elif operation == "REMOVE" and index is not None:
            patched["constraints"].pop(index)
        else:
            raise IRValidationError("constraint probe removal target is absent")
    elif family == "parameter" and operation == "SET":
        raise IRValidationError("parameter probes are unsupported until expressions consume parameters")
    else:
        raise IRValidationError("unsupported hypothetical variant")
    return validate_ir(patched)


def _variant_basis_verified(
    current_ir: ValidatedIR,
    variant: dict[str, Any],
    prompt_zh: str | None,
) -> bool:
    # V0 has no programmatic binder for free-form PROMPT numbers and no
    # preregistered range registry.  Until either exists, only an existing
    # binary action's disable counterfactual is admissible.  Eligibility=true
    # preserves [0, 1]; it never means that the action must be selected.
    if (
        variant.get("range_basis") != "MODEL_BOUNDARY"
        or variant.get("basis_quote") is not None
        or variant.get("operation") != "SET"
    ):
        return False
    family, slot = split_target(str(variant.get("target") or ""))
    value = variant.get("value")
    if family != "variable" or not isinstance(value, dict) or set(value) != {"lb", "ub"}:
        return False
    row = next((item for item in current_ir["variables"] if item["id"] == slot), None)
    return bool(
        row
        and row["type"] == "BINARY"
        and row["lb"] == 0.0
        and row["ub"] == 1.0
        and value["lb"] == 0
        and value["ub"] == 0
    )


def probe_gap(
    current_ir: ValidatedIR,
    base_capture: SolveCapture,
    target: str,
    variants: list[dict[str, Any]],
    output_schema: dict[str, Any] | None = None,
    prompt_zh: str | None = None,
) -> tuple[PotentialEffect, bool, dict[str, Any]]:
    if split_target(target)[0] == "parameter":
        return PotentialEffect.UNKNOWN, False, {"reason": "V0 compiler does not consume parameter metadata"}
    if not variants:
        return PotentialEffect.UNKNOWN, False, {"reason": "no bounded hypothetical variants"}
    captures: list[dict[str, Any]] = []
    priority = {
        PotentialEffect.UNKNOWN: -1,
        PotentialEffect.NO_EFFECT: 0,
        PotentialEffect.VALUE_CHANGE: 1,
        PotentialEffect.DECISION_CHANGE: 2,
        PotentialEffect.FEASIBILITY_CHANGE: 3,
    }
    strongest = PotentialEffect.NO_EFFECT
    for variant in variants[:3]:
        try:
            if not _variant_basis_verified(current_ir, variant, prompt_zh):
                raise IRValidationError("hypothetical variant basis is not program-verifiable")
            candidate_ir = _apply_hypothetical_variant(current_ir, variant, target)
            candidate_ir = validate_ir(candidate_ir, output_schema)
            capture = compile_and_solve(candidate_ir, output_schema)
            effect, delta = compare_solves(base_capture, capture)
            captures.append({"variant": copy.deepcopy(variant), "solve": delta})
            if priority[effect] > priority[strongest]:
                strongest = effect
        except (IRValidationError, SolverError) as exc:
            return PotentialEffect.UNKNOWN, False, {"reason": str(exc), "captures": captures}
    return strongest, True, {"captures": captures, "range_basis_verified": True}


def probe_all_gaps(
    state: DecisionCompleteORState,
    current_ir: ValidatedIR,
    variants_by_gap: dict[str, list[dict[str, Any]]],
    output_schema: dict[str, Any] | None = None,
    prompt_zh: str | None = None,
) -> DecisionCompleteORState:
    def exhaustive_binary_local(gap: Any, variants: list[dict[str, Any]]) -> bool:
        if gap.gap_route.value == "EXTERNAL_RULE":
            return False
        family, slot = split_target(gap.target)
        if family != "variable":
            return False
        row = next((item for item in current_ir["variables"] if item["id"] == slot), None)
        if not row or row["type"] != "BINARY" or row["lb"] != 0.0 or row["ub"] != 1.0:
            return False
        assignments: set[int] = set()
        for variant in variants:
            value = variant.get("value")
            if (
                variant.get("target") != gap.target
                or variant.get("operation") != "SET"
                or variant.get("range_basis") != "MODEL_BOUNDARY"
                or not isinstance(value, dict)
                or set(value) != {"lb", "ub"}
                or value["lb"] != value["ub"]
                or value["lb"] not in {0, 1}
            ):
                return False
            assignments.add(int(value["lb"]))
        return assignments == {0, 1}

    result = state
    for gap in list(result.gaps):
        if gap.state != GapState.OPEN:
            continue
        effect, coverage, diagnostic = probe_gap(
            current_ir,
            result.current_solve,
            gap.target,
            variants_by_gap.get(gap.gap_id, []),
            output_schema,
            prompt_zh,
        )
        result = apply_state_update(
            result,
            StateUpdate.probe(
                gap.gap_id,
                effect,
                coverage,
                str(diagnostic),
                exhaustive_local=coverage
                and exhaustive_binary_local(gap, variants_by_gap.get(gap.gap_id, [])),
            ),
        )
    return result


def apply_patch_and_solve(
    current_ir: ValidatedIR,
    bundle: PatchBundle,
    output_schema: dict[str, Any] | None = None,
) -> tuple[ValidatedIR, SolveCapture]:
    from .patch import apply_patch_transactionally

    candidate = apply_patch_transactionally(current_ir, bundle, output_schema)
    return candidate, compile_and_solve(candidate, output_schema)
