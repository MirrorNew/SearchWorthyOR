import gurobipy as gp
import json

model = gp.Model("SWOR065_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}
model.update()

objective = {
    "x_0": 1001, "x_1": 959, "x_2": 898, "x_3": 856,
    "x_4": 795, "x_5": 753, "x_6": 692
}
model.setObjective(gp.quicksum(objective[name] * x[name] for name in names), gp.GRB.MAXIMIZE)

rows = [
    ("holding_count_eq_3", "==", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1}),
    ("capital_occupancy_le_12", "<=", 12, {"x_0": 4, "x_1": 1, "x_2": 2, "x_3": 3, "x_4": 4, "x_5": 1, "x_6": 2}),
    ("risk_points_le_15", "<=", 15, {"x_0": 1, "x_1": 3, "x_2": 5, "x_3": 2, "x_4": 4, "x_5": 1, "x_6": 3}),
    ("external_strategy_A_ineligible", "==", 0, {"x_0": 1})
]

for row_name, sense, rhs, terms in rows:
    expr = gp.quicksum(coef * x[name] for name, coef in terms.items())
    if sense == "<=":
        model.addConstr(expr <= rhs, name=row_name)
    elif sense == ">=":
        model.addConstr(expr >= rhs, name=row_name)
    else:
        model.addConstr(expr == rhs, name=row_name)

model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: x[name].X for name in names}
    projected_action = [int(round(values[name])) for name in names]
    violations = []
    for row_name, sense, rhs, terms in rows:
        lhs = sum(coef * values[name] for name, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    bound_violations = [max(0.0, -values[name], values[name] - 1.0) for name in names]
    max_constraint_violation = max(violations + bound_violations)
    integrality_violation = max(abs(values[name] - round(values[name])) for name in names)
    objective_value = model.ObjVal
else:
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None
    objective_value = None

print(json.dumps({
    "status": status,
    "objective": objective_value,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))