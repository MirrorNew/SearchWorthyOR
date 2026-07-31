import gurobipy as gp
import json
import math

model = gp.Model("SWOR057")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
model.setObjective(
    1008 * x[0] + 947 * x[1] + 905 * x[2] +
    844 * x[3] + 802 * x[4] + 741 * x[5],
    gp.GRB.MAXIMIZE
)

model.addConstr(gp.quicksum(x) == 3, name="exactly_three_shift_blocks")
model.addConstr(x[0] + x[3] >= 1, name="period_1_coverage")
model.addConstr(x[1] + x[4] >= 1, name="period_2_coverage")
model.addConstr(x[2] + x[5] >= 1, name="period_3_coverage")

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
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    constraint_violations = [
        abs(sum(values) - 3.0),
        max(0.0, 1.0 - values[0] - values[3]),
        max(0.0, 1.0 - values[1] - values[4]),
        max(0.0, 1.0 - values[2] - values[5])
    ]
    bound_violations = [max(0.0, -value, value - 1.0) for value in values]
    max_constraint_violation = max(constraint_violations + bound_violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal)
else:
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None
    objective = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))