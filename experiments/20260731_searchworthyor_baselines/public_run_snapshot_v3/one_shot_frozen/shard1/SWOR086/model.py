import gurobipy as gp
import json
import math

model = gp.Model("SWOR086_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

objective_terms = {
    "x_0": 1002, "x_1": 960, "x_2": 899, "x_3": 857,
    "x_4": 796, "x_5": 735, "x_6": 693
}
model.setObjective(
    gp.quicksum(coef * x[name] for name, coef in objective_terms.items()),
    gp.GRB.MAXIMIZE
)

constraint_data = [
    ("c_exactly_three", "==", 3, {name: 1 for name in names}),
    ("c_subject_1", "<=", 1, {"x_0": 1, "x_3": 1, "x_6": 1}),
    ("c_subject_2", "<=", 1, {"x_1": 1, "x_4": 1}),
    ("c_subject_3", "<=", 1, {"x_2": 1, "x_5": 1}),
    ("c_core_minimum", ">=", 2, {"x_0": 1, "x_1": 1, "x_2": 1}),
    ("c_protection_minimum", ">=", 1, {"x_5": 1, "x_6": 1})
]

for cname, sense, rhs, terms in constraint_data:
    lhs = gp.quicksum(coef * x[name] for name, coef in terms.items())
    if sense == "<=":
        model.addConstr(lhs <= rhs, name=cname)
    elif sense == ">=":
        model.addConstr(lhs >= rhs, name=cname)
    else:
        model.addConstr(lhs == rhs, name=cname)

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: x[name].X for name in names}
    projected_action = [int(round(values[name])) for name in names]
    violations = []
    for cname, sense, rhs, terms in constraint_data:
        lhs_value = sum(coef * values[name] for name, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs_value - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs_value))
        else:
            violations.append(abs(lhs_value - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(values[name] - round(values[name])) for name in names)
    objective = model.ObjVal
else:
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
