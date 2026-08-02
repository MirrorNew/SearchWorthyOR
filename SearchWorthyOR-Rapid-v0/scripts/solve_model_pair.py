from __future__ import annotations

import argparse
from decimal import Decimal
import itertools
import json
import math
from pathlib import Path
from typing import Any

from coptpy import COPT, Envr, quicksum


TOL = 1e-8
MIN_SAFE_NONZERO_MAGNITUDE = Decimal("0.000001")
MAX_ENUMERATED_ASSIGNMENTS = 200_000


def exact_decimal(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("boolean is not a numeric model value")
    return Decimal(str(value))


def validate_numeric_scale(value: Any, location: str) -> None:
    number = exact_decimal(value)
    if not number.is_finite():
        raise ValueError(f"{location}: non-finite numeric value")
    if number != 0 and abs(number) < MIN_SAFE_NONZERO_MAGNITUDE:
        raise ValueError(f"{location}: unsafe sub-micro numeric magnitude")


def load_model(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version", "id", "variant", "family", "source_candidate_id",
        "variables", "objective", "constraints", "action_projection",
    }
    if set(value) != required or value["schema_version"] != "searchworthyor.rapid_model_ir.v0":
        raise ValueError(f"{path}: invalid top-level contract")
    names = [variable["name"] for variable in value["variables"]]
    if len(names) != len(set(names)):
        raise ValueError(f"{path}: duplicate variable")
    name_set = set(names)
    if not set(value["action_projection"]) <= name_set:
        raise ValueError(f"{path}: invalid action projection")
    for variable in value["variables"]:
        if variable["type"] not in {"BINARY", "INTEGER"}:
            raise ValueError(f"{path}: only finite discrete variables are allowed")
        if not isinstance(variable["lb"], int) or not isinstance(variable["ub"], int):
            raise ValueError(f"{path}: bounds must be integers")
        if variable["type"] == "BINARY" and (variable["lb"], variable["ub"]) != (0, 1):
            raise ValueError(f"{path}: binary bounds must be 0..1")
        if variable["lb"] > variable["ub"]:
            raise ValueError(f"{path}: invalid bounds")
    if value["variant"] == "base":
        nonfixed = {variable["name"] for variable in value["variables"] if variable["lb"] < variable["ub"]}
        if set(value["action_projection"]) != nonfixed:
            missing = sorted(nonfixed - set(value["action_projection"]))
            extra = sorted(set(value["action_projection"]) - nonfixed)
            raise ValueError(f"{path}: incomplete base action projection: missing={missing}, fixed={extra}")
    validate_numeric_scale(value["objective"]["constant"], f"{path}:objective.constant")
    for name, number in value["objective"]["coefficients"].items():
        validate_numeric_scale(number, f"{path}:objective.coefficients.{name}")
    for constraint in value["constraints"]:
        validate_numeric_scale(constraint["rhs"], f"{path}:constraint.{constraint['name']}.rhs")
        for name, number in constraint["coefficients"].items():
            validate_numeric_scale(number, f"{path}:constraint.{constraint['name']}.coefficients.{name}")
    for coefficients in [value["objective"]["coefficients"], *[c["coefficients"] for c in value["constraints"]]]:
        if not set(coefficients) <= name_set:
            raise ValueError(f"{path}: coefficient references unknown variable")
        if any(not math.isfinite(number) for number in coefficients.values()):
            raise ValueError(f"{path}: non-finite coefficient")
    return value


def objective_value(model: dict[str, Any], assignment: dict[str, int]) -> Decimal:
    return exact_decimal(model["objective"]["constant"]) + sum(
        (exact_decimal(coefficient) * assignment[name]
        for name, coefficient in model["objective"]["coefficients"].items()
        ),
        Decimal(0),
    )


def constraint_satisfied(constraint: dict[str, Any], assignment: dict[str, int]) -> bool:
    lhs = sum(
        float(coefficient) * assignment[name]
        for name, coefficient in constraint["coefficients"].items()
    )
    rhs = float(constraint["rhs"])
    if constraint["sense"] == "<=":
        return lhs <= rhs + TOL
    if constraint["sense"] == ">=":
        return lhs >= rhs - TOL
    return abs(lhs - rhs) <= TOL


def feasible(model: dict[str, Any], assignment: dict[str, int]) -> bool:
    for constraint in model["constraints"]:
        if not constraint_satisfied(constraint, assignment):
            return False
    return True


def redundant_constraints(model: dict[str, Any]) -> list[str]:
    variables = model["variables"]
    domains = [range(variable["lb"], variable["ub"] + 1) for variable in variables]
    count = math.prod(len(domain) for domain in domains)
    if count > MAX_ENUMERATED_ASSIGNMENTS:
        raise ValueError(f"enumeration limit exceeded: {count}")
    assignments = [
        {variable["name"]: value for variable, value in zip(variables, values, strict=True)}
        for values in itertools.product(*domains)
    ]
    redundant = []
    active = list(model["constraints"])
    for target in model["constraints"]:
        others = [constraint for constraint in active if constraint is not target]
        has_independence_witness = any(
            not constraint_satisfied(target, assignment)
            and all(constraint_satisfied(other, assignment) for other in others)
            for assignment in assignments
        )
        if not has_independence_witness:
            redundant.append(target["name"])
            active.remove(target)
    return redundant


def enumerate_optimal_actions(model: dict[str, Any]) -> tuple[float, list[dict[str, int]], int]:
    variables = model["variables"]
    domains = [range(variable["lb"], variable["ub"] + 1) for variable in variables]
    count = math.prod(len(domain) for domain in domains)
    if count > MAX_ENUMERATED_ASSIGNMENTS:
        raise ValueError(f"enumeration limit exceeded: {count}")
    best: Decimal | None = None
    actions: set[tuple[int, ...]] = set()
    projection = model["action_projection"]
    feasible_count = 0
    for values in itertools.product(*domains):
        assignment = {variable["name"]: value for variable, value in zip(variables, values, strict=True)}
        if not feasible(model, assignment):
            continue
        feasible_count += 1
        objective = objective_value(model, assignment)
        better = best is None or (
            model["objective"]["sense"] == "min" and objective < best
        ) or (
            model["objective"]["sense"] == "max" and objective > best
        )
        if better:
            best = objective
            actions = {tuple(assignment[name] for name in projection)}
        elif best is not None and objective == best:
            actions.add(tuple(assignment[name] for name in projection))
    if best is None:
        raise ValueError("enumeration found no feasible assignment")
    return float(best), [dict(zip(projection, values, strict=True)) for values in sorted(actions)], feasible_count


def solve_copt(model: dict[str, Any]) -> tuple[float, dict[str, int]]:
    env = Envr()
    problem = env.createModel(f"{model['id']}_{model['variant']}")
    problem.setParam(COPT.Param.Logging, 0)
    variables = {}
    for item in model["variables"]:
        variables[item["name"]] = problem.addVar(
            lb=item["lb"], ub=item["ub"],
            vtype=COPT.BINARY if item["type"] == "BINARY" else COPT.INTEGER,
            name=item["name"],
        )
    objective = float(model["objective"]["constant"]) + quicksum(
        float(coefficient) * variables[name]
        for name, coefficient in model["objective"]["coefficients"].items()
    )
    problem.setObjective(
        objective,
        COPT.MINIMIZE if model["objective"]["sense"] == "min" else COPT.MAXIMIZE,
    )
    for constraint in model["constraints"]:
        lhs = quicksum(
            float(coefficient) * variables[name]
            for name, coefficient in constraint["coefficients"].items()
        )
        if constraint["sense"] == "<=":
            problem.addConstr(lhs <= float(constraint["rhs"]), name=constraint["name"])
        elif constraint["sense"] == ">=":
            problem.addConstr(lhs >= float(constraint["rhs"]), name=constraint["name"])
        else:
            problem.addConstr(lhs == float(constraint["rhs"]), name=constraint["name"])
    problem.solve()
    if problem.status != COPT.OPTIMAL:
        raise ValueError(f"COPT status is {problem.status}, not OPTIMAL")
    solution = {name: int(round(variable.x)) for name, variable in variables.items()}
    return float(problem.objval), solution


def evaluate(base_path: Path, patched_path: Path) -> dict[str, Any]:
    base = load_model(base_path)
    patched = load_model(patched_path)
    if base["id"] != patched["id"] or base["action_projection"] != patched["action_projection"]:
        raise ValueError("base/patched identity or action projection mismatch")
    if base["variant"] != "base" or patched["variant"] != "patched":
        raise ValueError("variant mismatch")
    base_solver_obj, base_incumbent = solve_copt(base)
    patched_solver_obj, patched_incumbent = solve_copt(patched)
    base_enum_obj, base_actions, base_feasible = enumerate_optimal_actions(base)
    patched_enum_obj, patched_actions, patched_feasible = enumerate_optimal_actions(patched)
    if abs(base_solver_obj - base_enum_obj) > TOL or abs(patched_solver_obj - patched_enum_obj) > TOL:
        raise ValueError("solver/enumeration objective mismatch")
    action_names = base["action_projection"]
    base_keys = {tuple(action[name] for name in action_names) for action in base_actions}
    patched_keys = {tuple(action[name] for name in action_names) for action in patched_actions}
    common = sorted(base_keys & patched_keys)
    return {
        "schema_version": "searchworthyor.rapid_solve_result.v0",
        "id": base["id"],
        "solver": "COPT 8.0.5",
        "base_status": "OPTIMAL",
        "patched_status": "OPTIMAL",
        "base_objective": base_enum_obj,
        "patched_objective": patched_enum_obj,
        "base_incumbent": base_incumbent,
        "patched_incumbent": patched_incumbent,
        "base_feasible_assignment_count": base_feasible,
        "patched_feasible_assignment_count": patched_feasible,
        "base_optimal_actions": base_actions,
        "patched_optimal_actions": patched_actions,
        "common_optimal_actions": [dict(zip(action_names, values, strict=True)) for values in common],
        "common_optimal_action_feasible": bool(common),
        "optimal_action_changed": not bool(common),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--patched", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.base, args.patched)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
