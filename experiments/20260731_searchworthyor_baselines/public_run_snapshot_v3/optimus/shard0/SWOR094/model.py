import gurobipy as gp
from gurobipy import GRB
import json
import math

patched_ir = {
    "model_id": "SWOR094",
    "sense": "max",
    "single_objective": True,
    "variables": [
        {"name": "x_0", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_1", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_2", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_3", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_4", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_5", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_6", "vartype": "B", "lb": 0, "ub": 1}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1018, "x_1": 957, "x_2": 896, "x_3": 854, "x_4": 793, "x_5": 751, "x_6": 690}
    },
    "constraints": [
        {"name": "required_selected_shifts", "sense": "==", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1}},
        {"name": "period_1_coverage", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_3": 1, "x_6": 1}},
        {"name": "period_2_coverage", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_4": 1}},
        {"name": "period_3_coverage", "sense": ">=", "rhs": 1, "terms": {"x_2": 1, "x_5": 1}},
        {"name": "policy_A_ineligible", "sense": "==", "rhs": 0, "terms": {"x_0": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
}

model = gp.Model(patched_ir["model_id"])
model.Params.OutputFlag = 0
variables = {}
for spec in patched_ir["variables"]:
    variables[spec["name"]] = model.addVar(
        lb=spec["lb"],
        ub=spec["ub"],
        vtype=GRB.BINARY,
        name=spec["name"]
    )
model.update()

objective = gp.LinExpr(patched_ir["objective"]["constant"])
for name, coefficient in patched_ir["objective"]["terms"].items():
    objective += coefficient * variables[name]
model.setObjective(objective, GRB.MAXIMIZE)

for constraint in patched_ir["constraints"]:
    lhs = gp.quicksum(coefficient * variables[name] for name, coefficient in constraint["terms"].items())
    if constraint["sense"] == "<=":
        model.addConstr(lhs <= constraint["rhs"], name=constraint["name"])
    elif constraint["sense"] == ">=":
        model.addConstr(lhs >= constraint["rhs"], name=constraint["name"])
    elif constraint["sense"] == "==":
        model.addConstr(lhs == constraint["rhs"], name=constraint["name"])
    else:
        raise ValueError("Unsupported constraint sense: " + constraint["sense"])

model.optimize()

status_names = {
    1: "LOADED",
    2: "OPTIMAL",
    3: "INFEASIBLE",
    4: "INF_OR_UNBD",
    5: "UNBOUNDED",
    6: "CUTOFF",
    7: "ITERATION_LIMIT",
    8: "NODE_LIMIT",
    9: "TIME_LIMIT",
    10: "SOLUTION_LIMIT",
    11: "INTERRUPTED",
    12: "NUMERIC",
    13: "SUBOPTIMAL",
    14: "INPROGRESS",
    15: "USER_OBJ_LIMIT",
    16: "WORK_LIMIT",
    17: "MEM_LIMIT"
}

if model.SolCount > 0:
    values = {name: variables[name].X for name in variables}
    projected_action = [int(round(values[name])) for name in patched_ir["action_projection"]]
    integrality_violation = max(abs(value - round(value)) for value in values.values())
    violations = []
    for constraint in patched_ir["constraints"]:
        lhs_value = sum(coefficient * values[name] for name, coefficient in constraint["terms"].items())
        if constraint["sense"] == "<=":
            violation = max(0.0, lhs_value - constraint["rhs"])
        elif constraint["sense"] == ">=":
            violation = max(0.0, constraint["rhs"] - lhs_value)
        else:
            violation = abs(lhs_value - constraint["rhs"])
        violations.append(violation)
    max_constraint_violation = max(violations) if violations else 0.0
    objective_value = model.ObjVal
else:
    projected_action = []
    integrality_violation = None
    max_constraint_violation = None
    objective_value = None

result = {
    "status": status_names.get(model.Status, "STATUS_" + str(model.Status)),
    "objective": objective_value,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
