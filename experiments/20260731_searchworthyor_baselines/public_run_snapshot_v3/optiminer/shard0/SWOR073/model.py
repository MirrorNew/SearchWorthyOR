import gurobipy as gp
import json
import math

model = gp.Model("SWOR073_patched")
model.Params.OutputFlag = 0

projection = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in projection}

objective_terms = {
    "x_0": 1004,
    "x_1": 962,
    "x_2": 901,
    "x_3": 859,
    "x_4": 798,
    "x_5": 737,
}
model.setObjective(gp.quicksum(coef * x[name] for name, coef in objective_terms.items()), gp.GRB.MAXIMIZE)

constraint_specs = [
    ("required_assignments", "==", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}),
    ("subject1_mutex", "<=", 1, {"x_0": 1, "x_3": 1}),
    ("subject2_frozen_mutex", "<=", 1, {"x_1": 1, "x_4": 1}),
    ("subject3_mutex", "<=", 1, {"x_2": 1, "x_5": 1}),
    ("terminal_backup_mutex", "<=", 1, {"x_4": 1, "x_5": 1}),
    ("policy_AB_mutex", "<=", 1, {"x_0": 1, "x_1": 1}),
]

for cname, sense, rhs, terms in constraint_specs:
    expr = gp.quicksum(coef * x[name] for name, coef in terms.items())
    if sense == "<=":
        model.addConstr(expr <= rhs, name=cname)
    elif sense == ">=":
        model.addConstr(expr >= rhs, name=cname)
    else:
        model.addConstr(expr == rhs, name=cname)

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: x[name].X for name in projection}
    projected_action = [int(round(values[name])) for name in projection]
    violations = []
    for cname, sense, rhs, terms in constraint_specs:
        lhs = math.fsum(coef * values[name] for name, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values.values())
    objective = model.ObjVal
else:
    projected_action = [0 for _ in projection]
    max_constraint_violation = None
    integrality_violation = None
    objective = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}, ensure_ascii=False))
