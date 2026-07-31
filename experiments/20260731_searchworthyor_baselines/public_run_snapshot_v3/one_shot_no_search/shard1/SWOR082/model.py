import gurobipy as gp
import json

model = gp.Model("SWOR082")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = [
    model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}")
    for i in range(6)
]

profits = [1007.0, 965.0, 904.0, 843.0, 801.0, 740.0]
model.setObjective(
    gp.quicksum(profits[i] * x[i] for i in range(6)),
    gp.GRB.MAXIMIZE,
)

model.addConstr(x[0] + x[3] == 1.0, name="chain_segment_1_exactly_one")
model.addConstr(x[1] + x[4] == 1.0, name="chain_segment_2_exactly_one")
model.addConstr(x[2] + x[5] == 1.0, name="chain_segment_3_exactly_one")
model.addConstr(x[4] + x[5] <= 1.0, name="terminal_backups_mutual_exclusion")

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
    values = [float(x[i].X) for i in range(6)]
    projected_action = [1 if value >= 0.5 else 0 for value in values]
    row_violations = [
        abs(values[0] + values[3] - 1.0),
        abs(values[1] + values[4] - 1.0),
        abs(values[2] + values[5] - 1.0),
        max(0.0, values[4] + values[5] - 1.0),
    ]
    bound_violations = [
        max(0.0, -value, value - 1.0) for value in values
    ]
    max_constraint_violation = max(row_violations + bound_violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal)
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
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False))
