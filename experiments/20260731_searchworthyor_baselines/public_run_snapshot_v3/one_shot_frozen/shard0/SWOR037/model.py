import gurobipy as gp
import json
import math

model = gp.Model("SWOR037_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}
model.update()

objective_terms = {
    "x_0": 1013, "x_1": 952, "x_2": 910, "x_3": 849,
    "x_4": 788, "x_5": 746, "x_6": 685, "x_7": 643
}
model.setObjective(gp.quicksum(coef * x[name] for name, coef in objective_terms.items()), gp.GRB.MAXIMIZE)

constraints_data = [
    ("module_count_limit", "<=", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1, "x_7": 1}),
    ("zone_1_connectivity", ">=", 1, {"x_0": 1, "x_3": 1, "x_6": 1}),
    ("zone_2_connectivity", ">=", 1, {"x_1": 1, "x_4": 1, "x_7": 1}),
    ("zone_3_connectivity", ">=", 1, {"x_2": 1, "x_5": 1}),
    ("primary_access_backhaul", ">=", 0, {"x_0": -1, "x_1": 1, "x_4": 1}),
    ("core_candidate_requirement", ">=", 1, {"x_0": 1, "x_3": 1}),
    ("rest_window_coverage", "<=", 1, {"x_0": 1, "x_1": 1, "x_6": -1, "x_7": -1})
]

for cname, sense, rhs, terms in constraints_data:
    expr = gp.quicksum(coef * x[name] for name, coef in terms.items())
    if sense == "<=":
        model.addConstr(expr <= rhs, name=cname)
    elif sense == ">=":
        model.addConstr(expr >= rhs, name=cname)
    else:
        model.addConstr(expr == rhs, name=cname)

model.optimize()
status_code = model.Status
status = "OPTIMAL" if status_code == gp.GRB.OPTIMAL else "STATUS_" + str(status_code)

if model.SolCount > 0:
    raw = {name: x[name].X for name in names}
    projected_action = [int(round(raw[name])) for name in names]
    objective = float(model.ObjVal)
    violations = []
    for cname, sense, rhs, terms in constraints_data:
        lhs = sum(coef * raw[name] for name, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(raw[name] - round(raw[name])) for name in names)
else:
    projected_action = None
    objective = None
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))
