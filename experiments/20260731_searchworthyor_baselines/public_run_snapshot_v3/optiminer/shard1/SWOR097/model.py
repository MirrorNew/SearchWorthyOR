import gurobipy as gp
import json
import math

model = gp.Model("SWOR097_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}
model.update()

objective = {
    "x_0": 1012, "x_1": 951, "x_2": 909, "x_3": 848,
    "x_4": 806, "x_5": 745, "x_6": 684, "x_7": 642
}
model.setObjective(gp.quicksum(objective[name] * x[name] for name in names), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x[name] for name in names) == 3, name="frozen_exactly_3")
model.addConstr(x["x_0"] + x["x_3"] + x["x_6"] <= 1, name="subject1_at_most_1")
model.addConstr(x["x_1"] + x["x_4"] + x["x_7"] <= 1, name="subject2_at_most_1")
model.addConstr(x["x_2"] + x["x_5"] <= 1, name="subject3_at_most_1")
model.addConstr(x["x_0"] + x["x_1"] + x["x_2"] >= 2, name="core_at_least_2")
model.addConstr(x["x_0"] + x["x_1"] <= 1, name="policy_A_B_mutex")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: float(x[name].X) for name in names}
    projected_action = [int(round(values[name])) for name in names]
    objective_value = float(model.ObjVal)

    checks = [
        (sum(values[name] for name in names), "==", 3.0),
        (values["x_0"] + values["x_3"] + values["x_6"], "<=", 1.0),
        (values["x_1"] + values["x_4"] + values["x_7"], "<=", 1.0),
        (values["x_2"] + values["x_5"], "<=", 1.0),
        (values["x_0"] + values["x_1"] + values["x_2"], ">=", 2.0),
        (values["x_0"] + values["x_1"], "<=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(values[name] - round(values[name])) for name in names)
else:
    objective_value = None
    projected_action = [0 for name in names]
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective_value,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))