import gurobipy as gp
import json
import math

model = gp.Model("SWOR001_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
objective_terms = {
    "x_0": 1015, "x_1": 954, "x_2": 912,
    "x_3": 851, "x_4": 790, "x_5": 748
}
constraint_data = [
    ("mode_count_limit", "<=", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}),
    ("equipment_capacity_limit", "<=", 7, {"x_0": 4, "x_1": 1, "x_2": 2, "x_3": 3, "x_4": 4, "x_5": 1}),
    ("backup_E_F_mutex", "<=", 1, {"x_4": 1, "x_5": 1}),
    ("policy_A_B_incompatibility", "<=", 1, {"x_0": 1, "x_1": 1})
]

x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}
model.setObjective(gp.quicksum(objective_terms[name] * x[name] for name in names), gp.GRB.MAXIMIZE)

for constraint_name, sense, rhs, terms in constraint_data:
    lhs = gp.quicksum(coef * x[name] for name, coef in terms.items())
    if sense == "<=":
        model.addConstr(lhs <= rhs, name=constraint_name)
    elif sense == ">=":
        model.addConstr(lhs >= rhs, name=constraint_name)
    else:
        model.addConstr(lhs == rhs, name=constraint_name)

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
    integrality_violation = max(abs(values[name] - round(values[name])) for name in names)
    max_constraint_violation = 0.0
    for constraint_name, sense, rhs, terms in constraint_data:
        lhs_value = sum(coef * values[name] for name, coef in terms.items())
        if sense == "<=":
            violation = max(0.0, lhs_value - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs_value)
        else:
            violation = abs(lhs_value - rhs)
        max_constraint_violation = max(max_constraint_violation, violation)
    for name in names:
        max_constraint_violation = max(max_constraint_violation, max(0.0, -values[name]), max(0.0, values[name] - 1.0))
    objective = model.ObjVal
else:
    projected_action = []
    integrality_violation = None
    max_constraint_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
