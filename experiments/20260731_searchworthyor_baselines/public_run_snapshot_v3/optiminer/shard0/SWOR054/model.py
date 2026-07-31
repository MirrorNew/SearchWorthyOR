import gurobipy as gp
import json
import math

model = gp.Model("SWOR054_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
utilities = [1014, 953, 911, 850, 789, 747, 686]
resource_points = [2, 3, 4, 1, 2, 3, 4]
categories = ["基础类别", "基础类别", "基础类别", "基础类别", "基础类别", "保障类别1", "保障类别2"]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="exactly_three_assignments")
model.addConstr(x[0] + x[3] + x[6] <= 1, name="subject_1_at_most_one")
model.addConstr(x[1] + x[4] <= 1, name="subject_2_at_most_one")
model.addConstr(x[2] + x[5] <= 1, name="subject_3_at_most_one")
model.addConstr(x[5] + x[6] <= 1, name="terminal_reserves_mutex")
model.addConstr(x[5] + x[6] >= 1, name="applicable保障_at_least_one")

model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, "STATUS_" + str(model.Status))

if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal) if math.isfinite(model.ObjVal) else None
    lhs_values = [
        sum(values),
        values[0] + values[3] + values[6],
        values[1] + values[4],
        values[2] + values[5],
        values[5] + values[6],
        values[5] + values[6]
    ]
    senses = ["==", "<=", "<=", "<=", "<=", ">="]
    rhs_values = [3.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    violations = []
    for lhs, sense, rhs in zip(lhs_values, senses, rhs_values):
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0]
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