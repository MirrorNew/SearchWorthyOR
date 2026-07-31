import gurobipy as gp
import json

model = gp.Model("SWOR096_patched")
model.Params.OutputFlag = 0

x = [
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}")
    for i in range(8)
]

revenues = [1016, 955, 894, 852, 791, 749, 688, 646]
model.setObjective(
    gp.quicksum(revenues[i] * x[i] for i in range(8)),
    gp.GRB.MAXIMIZE,
)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="period_1_coverage")
model.addConstr(x[1] + x[4] + x[7] >= 1, name="period_2_coverage")
model.addConstr(x[2] + x[5] >= 1, name="period_3_coverage")
model.addConstr(x[6] + x[7] <= 1, name="g_h_mutual_exclusion")
model.addConstr(x[6] + x[7] >= 1, name="safeguard_minimum")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]

    activities = [
        sum(values),
        values[0] + values[3] + values[6],
        values[1] + values[4] + values[7],
        values[2] + values[5],
        values[6] + values[7],
        values[6] + values[7],
    ]
    constraint_violations = [
        abs(activities[0] - 3.0),
        max(0.0, 1.0 - activities[1]),
        max(0.0, 1.0 - activities[2]),
        max(0.0, 1.0 - activities[3]),
        max(0.0, activities[4] - 1.0),
        max(0.0, 1.0 - activities[5]),
    ]
    bound_violations = [
        max(0.0, -value, value - 1.0) for value in values
    ]
    max_constraint_violation = max(constraint_violations + bound_violations)
    integrality_violation = max(
        abs(value - round(value)) for value in values
    )
    objective = float(model.ObjVal)
else:
    objective = None
    projected_action = [0] * 8
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
