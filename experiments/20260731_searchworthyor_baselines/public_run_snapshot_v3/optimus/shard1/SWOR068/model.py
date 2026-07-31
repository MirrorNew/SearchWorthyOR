import gurobipy as gp
import json

patched_ir = {
    "model_id": "SWOR068_patched",
    "sense": "max",
    "variables": [
        {"name": "x_0", "lb": 0, "ub": 1},
        {"name": "x_1", "lb": 0, "ub": 1},
        {"name": "x_2", "lb": 0, "ub": 1},
        {"name": "x_3", "lb": 0, "ub": 1},
        {"name": "x_4", "lb": 0, "ub": 1},
        {"name": "x_5", "lb": 0, "ub": 1}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1008, "x_1": 947, "x_2": 905, "x_3": 844, "x_4": 802, "x_5": 741}
    },
    "constraints": [
        {"name": "select_exactly_3", "sense": "==", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}},
        {"name": "emergency_coverage", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}},
        {"name": "continuity_coverage", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_2": 1}},
        {"name": "specialty_coverage", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_2": 1}},
        {"name": "core_minimum", "sense": ">=", "rhs": 2, "terms": {"x_0": 1, "x_1": 1, "x_2": 1}},
        {"name": "compliance_A_forbids_B", "sense": "<=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
}

model = gp.Model(patched_ir["model_id"])
model.Params.OutputFlag = 0
variables = {}
for spec in patched_ir["variables"]:
    variables[spec["name"]] = model.addVar(
        lb=spec["lb"], ub=spec["ub"], vtype=gp.GRB.BINARY, name=spec["name"]
    )
model.update()

objective = gp.LinExpr(patched_ir["objective"]["constant"])
for name, coefficient in patched_ir["objective"]["terms"].items():
    objective += coefficient * variables[name]
model.setObjective(objective, gp.GRB.MAXIMIZE)

for constraint in patched_ir["constraints"]:
    expression = gp.LinExpr()
    for name, coefficient in constraint["terms"].items():
        expression += coefficient * variables[name]
    if constraint["sense"] == "<=":
        model.addConstr(expression <= constraint["rhs"], name=constraint["name"])
    elif constraint["sense"] == ">=":
        model.addConstr(expression >= constraint["rhs"], name=constraint["name"])
    else:
        model.addConstr(expression == constraint["rhs"], name=constraint["name"])

model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))
projected_action = []
objective_value = None
max_constraint_violation = None
integrality_violation = None

if model.SolCount > 0:
    values = {name: variables[name].X for name in variables}
    projected_action = [int(round(values[name])) for name in patched_ir["action_projection"]]
    objective_value = float(model.ObjVal)
    max_constraint_violation = 0.0
    for constraint in patched_ir["constraints"]:
        activity = sum(coefficient * values[name] for name, coefficient in constraint["terms"].items())
        if constraint["sense"] == "<=":
            violation = max(0.0, activity - constraint["rhs"])
        elif constraint["sense"] == ">=":
            violation = max(0.0, constraint["rhs"] - activity)
        else:
            violation = abs(activity - constraint["rhs"])
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(abs(value - round(value)) for value in values.values())

result = {
    "status": status,
    "objective": objective_value,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
