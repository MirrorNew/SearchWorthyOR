import gurobipy as gp
import json
import math

patched_ir = {
    "model_id": "SWOR080",
    "world": "evidence_patched",
    "sense": "max",
    "single_objective": True,
    "variables": [
        {"name": "x_0", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "策略包A"},
        {"name": "x_1", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "策略包B"},
        {"name": "x_2", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "策略包C"},
        {"name": "x_3", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "策略包D"},
        {"name": "x_4", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "策略包E"},
        {"name": "x_5", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "策略包F"},
        {"name": "x_6", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "策略包G"},
        {"name": "x_7", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "策略包H"}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1012, "x_1": 951, "x_2": 909, "x_3": 848, "x_4": 806, "x_5": 745, "x_6": 684, "x_7": 642}
    },
    "constraints": [
        {"name": "position_count", "sense": "==", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1, "x_7": 1}},
        {"name": "capital_capacity", "sense": "<=", "rhs": 12, "terms": {"x_0": 4, "x_1": 1, "x_2": 2, "x_3": 3, "x_4": 4, "x_5": 1, "x_6": 2, "x_7": 3}},
        {"name": "risk_capacity", "sense": "<=", "rhs": 15, "terms": {"x_0": 5, "x_1": 2, "x_2": 4, "x_3": 1, "x_4": 3, "x_5": 5, "x_6": 2, "x_7": 4}},
        {"name": "core_choice_exactly_one", "sense": "==", "rhs": 1, "terms": {"x_1": 1, "x_4": 1, "x_7": 1}},
        {"name": "same_vehicle_credit_branch_exclusivity", "sense": "<=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
}

model = gp.Model(patched_ir["model_id"])
model.Params.OutputFlag = 0
model.Params.MIPGap = 0

x = {}
for spec in patched_ir["variables"]:
    x[spec["name"]] = model.addVar(
        lb=spec["lb"],
        ub=spec["ub"],
        vtype=gp.GRB.BINARY,
        name=spec["name"]
    )
model.update()

objective = patched_ir["objective"]["constant"] + gp.quicksum(
    coefficient * x[name]
    for name, coefficient in patched_ir["objective"]["terms"].items()
)
model.setObjective(objective, gp.GRB.MAXIMIZE)

for constraint in patched_ir["constraints"]:
    lhs = gp.quicksum(
        coefficient * x[name]
        for name, coefficient in constraint["terms"].items()
    )
    if constraint["sense"] == "<=":
        model.addConstr(lhs <= constraint["rhs"], name=constraint["name"])
    elif constraint["sense"] == ">=":
        model.addConstr(lhs >= constraint["rhs"], name=constraint["name"])
    else:
        model.addConstr(lhs == constraint["rhs"], name=constraint["name"])

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))
has_solution = model.SolCount > 0

if has_solution:
    values = {name: x[name].X for name in x}
    projected_action = [int(values[name] >= 0.5) for name in patched_ir["action_projection"]]
    max_constraint_violation = 0.0
    for constraint in patched_ir["constraints"]:
        lhs_value = sum(coefficient * values[name] for name, coefficient in constraint["terms"].items())
        rhs = constraint["rhs"]
        if constraint["sense"] == "<=":
            violation = max(0.0, lhs_value - rhs)
        elif constraint["sense"] == ">=":
            violation = max(0.0, rhs - lhs_value)
        else:
            violation = abs(lhs_value - rhs)
        max_constraint_violation = max(max_constraint_violation, violation)
    for spec in patched_ir["variables"]:
        value = values[spec["name"]]
        max_constraint_violation = max(
            max_constraint_violation,
            max(0.0, spec["lb"] - value),
            max(0.0, value - spec["ub"])
        )
    integrality_violation = max(abs(values[name] - round(values[name])) for name in values)
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max_constraint_violation,
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0 for _ in patched_ir["action_projection"]],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))