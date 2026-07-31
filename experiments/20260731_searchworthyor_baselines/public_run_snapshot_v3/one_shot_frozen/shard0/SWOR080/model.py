import gurobipy as gp
import json
import math

patched_ir = {
    "model_id": "SWOR080_patched",
    "world": "patched",
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
        {"name": "core_backup_emergency_exactly_one", "sense": "==", "rhs": 1, "terms": {"x_1": 1, "x_4": 1, "x_7": 1}},
        {"name": "irs_30d_45w_same_vehicle_exclusivity", "sense": "<=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
}

model = gp.Model(patched_ir["model_id"])
model.Params.OutputFlag = 0
variables = {}
for spec in patched_ir["variables"]:
    variables[spec["name"]] = model.addVar(
        lb=spec["lb"],
        ub=spec["ub"],
        vtype=gp.GRB.BINARY,
        name=spec["name"]
    )
model.update()

objective = patched_ir["objective"]["constant"] + gp.quicksum(
    coefficient * variables[name]
    for name, coefficient in patched_ir["objective"]["terms"].items()
)
model.setObjective(objective, gp.GRB.MAXIMIZE)

for constraint in patched_ir["constraints"]:
    lhs = gp.quicksum(
        coefficient * variables[name]
        for name, coefficient in constraint["terms"].items()
    )
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
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))
has_solution = model.SolCount > 0

if has_solution:
    values = {name: float(variable.X) for name, variable in variables.items()}
    projected_action = [int(round(values[name])) for name in patched_ir["action_projection"]]
    objective_value = float(model.ObjVal) if math.isfinite(model.ObjVal) else None
    violations = []
    for constraint in patched_ir["constraints"]:
        lhs_value = sum(
            coefficient * values[name]
            for name, coefficient in constraint["terms"].items()
        )
        if constraint["sense"] == "<=":
            violations.append(max(0.0, lhs_value - constraint["rhs"]))
        elif constraint["sense"] == ">=":
            violations.append(max(0.0, constraint["rhs"] - lhs_value))
        else:
            violations.append(abs(lhs_value - constraint["rhs"]))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(
        abs(values[name] - round(values[name]))
        for name in patched_ir["action_projection"]
    )
else:
    projected_action = [0 for _ in patched_ir["action_projection"]]
    objective_value = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective_value,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))