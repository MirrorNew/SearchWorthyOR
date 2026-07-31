import gurobipy
import json
import math

model = gurobipy.Model("SWOR004_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
x = {name: model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

objective_terms = {
    "x_0": 1010,
    "x_1": 949,
    "x_2": 907,
    "x_3": 846,
    "x_4": 804,
    "x_5": 743,
    "x_6": 682
}
model.setObjective(
    gurobipy.quicksum(coef * x[name] for name, coef in objective_terms.items()),
    gurobipy.GRB.MAXIMIZE
)

constraint_specs = [
    ("frozen_exactly_3", "==", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1}),
    ("front_segment_cover", ">=", 1, {"x_0": 1, "x_1": 1, "x_3": 1, "x_6": 1}),
    ("rear_segment_cover", ">=", 1, {"x_1": 1, "x_2": 1, "x_4": 1}),
    ("core_at_least_2", ">=", 2, {"x_0": 1, "x_1": 1, "x_2": 1}),
    ("policy_A_ineligible", "==", 0, {"x_0": 1})
]

for constraint_name, constraint_sense, rhs, terms in constraint_specs:
    expression = gurobipy.quicksum(coef * x[name] for name, coef in terms.items())
    if constraint_sense == "==":
        model.addConstr(expression == rhs, name=constraint_name)
    elif constraint_sense == ">=":
        model.addConstr(expression >= rhs, name=constraint_name)
    else:
        model.addConstr(expression <= rhs, name=constraint_name)

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: x[name].X for name in names}
    projected_action = [int(round(values[name])) for name in names]
    integrality_violation = max(abs(values[name] - round(values[name])) for name in names)
    violations = []
    for constraint_name, constraint_sense, rhs, terms in constraint_specs:
        lhs = sum(coef * values[name] for name, coef in terms.items())
        if constraint_sense == "==":
            violations.append(abs(lhs - rhs))
        elif constraint_sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
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
