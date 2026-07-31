import gurobipy as gp
import json
import math

model = gp.Model("SWOR051_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

objective_terms = {
    "x_0": 1004,
    "x_1": 962,
    "x_2": 901,
    "x_3": 859,
    "x_4": 798,
    "x_5": 737
}
model.setObjective(gp.quicksum(coef * x[name] for name, coef in objective_terms.items()), gp.GRB.MAXIMIZE)

constraints = [
    {"name": "module_count_cap", "sense": "<=", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}},
    {"name": "zone_1_connectivity", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_3": 1}},
    {"name": "zone_2_connectivity", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_4": 1}},
    {"name": "zone_3_connectivity", "sense": ">=", "rhs": 1, "terms": {"x_2": 1, "x_5": 1}},
    {"name": "access_backhaul_link", "sense": ">=", "rhs": 0, "terms": {"x_0": -1, "x_1": 1, "x_4": 1}},
    {"name": "core_candidate_requirement", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_3": 1}},
    {"name": "policy_A_B_mutex", "sense": "<=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}}
]

for spec in constraints:
    expr = gp.quicksum(coef * x[name] for name, coef in spec["terms"].items())
    if spec["sense"] == "<=":
        model.addConstr(expr <= spec["rhs"], name=spec["name"])
    elif spec["sense"] == ">=":
        model.addConstr(expr >= spec["rhs"], name=spec["name"])
    else:
        model.addConstr(expr == spec["rhs"], name=spec["name"])

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: float(x[name].X) for name in names}
    projected_action = [1 if values[name] >= 0.5 else 0 for name in names]
    max_constraint_violation = 0.0
    for spec in constraints:
        lhs = sum(coef * values[name] for name, coef in spec["terms"].items())
        if spec["sense"] == "<=":
            violation = max(0.0, lhs - spec["rhs"])
        elif spec["sense"] == ">=":
            violation = max(0.0, spec["rhs"] - lhs)
        else:
            violation = abs(lhs - spec["rhs"])
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(abs(values[name] - round(values[name])) for name in names)
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": float(max_constraint_violation),
        "integrality_violation": float(integrality_violation)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))