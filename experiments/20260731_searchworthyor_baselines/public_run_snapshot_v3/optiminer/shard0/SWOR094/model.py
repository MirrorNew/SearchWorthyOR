import gurobipy as gp
import json
import math

model = gp.Model("SWOR094")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
benefits = {
    "x_0": 1018,
    "x_1": 957,
    "x_2": 896,
    "x_3": 854,
    "x_4": 793,
    "x_5": 751,
    "x_6": 690
}
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

model.setObjective(gp.quicksum(benefits[name] * x[name] for name in names), gp.GRB.MAXIMIZE)

constraint_data = [
    ("select_exactly_3", "==", 3, {name: 1 for name in names}),
    ("cover_period_1", ">=", 1, {"x_0": 1, "x_3": 1, "x_6": 1}),
    ("cover_period_2", ">=", 1, {"x_1": 1, "x_4": 1}),
    ("cover_period_3", ">=", 1, {"x_2": 1, "x_5": 1}),
    ("policy_A_ineligible", "==", 0, {"x_0": 1})
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
    max_constraint_violation = 0.0
    for cname, sense, rhs, terms in constraint_data:
        lhs_value = sum(coef * values[name] for name, coef in terms.items())
        if sense == "<=":
            violation = max(0.0, lhs_value - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs_value)
        else:
            violation = abs(lhs_value - rhs)
        max_constraint_violation = max(max_constraint_violation, violation)
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
