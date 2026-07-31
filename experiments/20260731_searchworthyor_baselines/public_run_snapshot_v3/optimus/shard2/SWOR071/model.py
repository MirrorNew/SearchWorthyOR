import gurobipy as gp
import json
import math

ir = {
    "model_id": "SWOR071_patched",
    "world": "patched",
    "sense": "max",
    "single_objective": True,
    "variables": [
        {"name": "x_0", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "服务单元A"},
        {"name": "x_1", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "服务单元B"},
        {"name": "x_2", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "服务单元C"},
        {"name": "x_3", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "服务单元D"},
        {"name": "x_4", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "服务单元E"},
        {"name": "x_5", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "服务单元F"},
        {"name": "x_6", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "服务单元G"}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1006, "x_1": 964, "x_2": 903, "x_3": 842, "x_4": 800, "x_5": 739, "x_6": 697}
    },
    "constraints": [
        {"name": "enable_exactly_3", "sense": "==", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1}},
        {"name": "emergency_coverage", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}},
        {"name": "continuity_coverage", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_2": 1}},
        {"name": "specialty_coverage", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_2": 1}},
        {"name": "core_or_backup", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_3": 1}},
        {"name": "compliance_A_excludes_B", "sense": "<=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
}

model = gp.Model(ir["model_id"])
model.Params.OutputFlag = 0
x = {}
for variable in ir["variables"]:
    x[variable["name"]] = model.addVar(
        lb=variable["lb"],
        ub=variable["ub"],
        vtype=gp.GRB.BINARY,
        name=variable["name"]
    )

objective = gp.LinExpr(ir["objective"]["constant"])
for name, coefficient in ir["objective"]["terms"].items():
    objective.addTerms(coefficient, x[name])
model.setObjective(objective, gp.GRB.MAXIMIZE)

for constraint in ir["constraints"]:
    expression = gp.LinExpr()
    for name, coefficient in constraint["terms"].items():
        expression.addTerms(coefficient, x[name])
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
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: x[name].X for name in x}
    projected_action = [int(round(values[name])) for name in ir["action_projection"]]
    max_constraint_violation = 0.0
    for constraint in ir["constraints"]:
        lhs = sum(coefficient * values[name] for name, coefficient in constraint["terms"].items())
        if constraint["sense"] == "<=":
            violation = max(0.0, lhs - constraint["rhs"])
        elif constraint["sense"] == ">=":
            violation = max(0.0, constraint["rhs"] - lhs)
        else:
            violation = abs(lhs - constraint["rhs"])
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(abs(value - round(value)) for value in values.values())
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
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))