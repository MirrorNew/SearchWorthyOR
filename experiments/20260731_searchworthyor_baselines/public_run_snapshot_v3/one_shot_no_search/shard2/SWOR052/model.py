import gurobipy as gp
import json
import math

model = gp.Model("SWOR052")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}
model.update()

objective_terms = {
    "x_0": 1006,
    "x_1": 964,
    "x_2": 903,
    "x_3": 842,
    "x_4": 800,
    "x_5": 739,
    "x_6": 697,
    "x_7": 636
}
model.setObjective(gp.quicksum(coef * x[name] for name, coef in objective_terms.items()), gp.GRB.MAXIMIZE)

constraint_data = [
    ("required_assignments", "==", 3, {name: 1 for name in names}),
    ("resource_subject_1_cap", "<=", 1, {"x_0": 1, "x_3": 1, "x_6": 1}),
    ("resource_subject_2_cap", "<=", 1, {"x_1": 1, "x_4": 1, "x_7": 1}),
    ("resource_subject_3_cap", "<=", 1, {"x_2": 1, "x_5": 1})
]

for constraint_name, sense, rhs, terms in constraint_data:
    expression = gp.quicksum(coef * x[name] for name, coef in terms.items())
    if sense == "==":
        model.addConstr(expression == rhs, name=constraint_name)
    elif sense == "<=":
        model.addConstr(expression <= rhs, name=constraint_name)
    else:
        model.addConstr(expression >= rhs, name=constraint_name)

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
    values = {name: x[name].X for name in names}
    projected_action = [int(round(values[name])) for name in names]
    objective = model.ObjVal
    violations = []
    for constraint_name, sense, rhs, terms in constraint_data:
        lhs = sum(coef * values[name] for name, coef in terms.items())
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(min(abs(values[name]), abs(values[name] - 1.0)) for name in names)
else:
    objective = None
    projected_action = [0 for name in names]
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))