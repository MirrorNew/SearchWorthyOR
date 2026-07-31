import gurobipy as gp
import json
import math

model = gp.Model("SWOR084_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}
model.update()

objective_terms = {
    "x_0": 1009, "x_1": 948, "x_2": 906, "x_3": 845,
    "x_4": 803, "x_5": 742, "x_6": 700, "x_7": 639
}
model.setObjective(
    gp.quicksum(coef * x[name] for name, coef in objective_terms.items()),
    gp.GRB.MAXIMIZE
)

rows = [
    ("segment_1_exactly_one", "==", 1.0, {"x_0": 1.0, "x_3": 1.0, "x_6": 1.0}),
    ("segment_2_exactly_one", "==", 1.0, {"x_1": 1.0, "x_4": 1.0, "x_7": 1.0}),
    ("segment_3_exactly_one", "==", 1.0, {"x_2": 1.0, "x_5": 1.0}),
    ("policy_ab_mutex", "<=", 1.0, {"x_0": 1.0, "x_1": 1.0})
]

for row_name, row_sense, rhs, terms in rows:
    lhs = gp.quicksum(coef * x[name] for name, coef in terms.items())
    if row_sense == "==":
        model.addConstr(lhs == rhs, name=row_name)
    elif row_sense == "<=":
        model.addConstr(lhs <= rhs, name=row_name)
    else:
        model.addConstr(lhs >= rhs, name=row_name)

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
    for row_name, row_sense, rhs, terms in rows:
        lhs_value = sum(coef * values[name] for name, coef in terms.items())
        if row_sense == "==":
            violations.append(abs(lhs_value - rhs))
        elif row_sense == "<=":
            violations.append(max(0.0, lhs_value - rhs))
        else:
            violations.append(max(0.0, rhs - lhs_value))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(values[name] - round(values[name])) for name in names)
    objective = model.ObjVal
else:
    projected_action = [0 for _ in names]
    max_constraint_violation = math.inf
    integrality_violation = math.inf
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
