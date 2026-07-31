import gurobipy as gp
import json
import math

model = gp.Model("SWOR042")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

objective_coefficients = [1002, 960, 899, 857, 796, 735]
model.setObjective(gp.quicksum(objective_coefficients[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="enable_exactly_three")
model.addConstr(x[0] + x[3] >= 1, name="period_1_cover")
model.addConstr(x[1] + x[4] >= 1, name="period_2_cover")
model.addConstr(x[2] + x[5] >= 1, name="period_3_cover")
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_backup_D")

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
    raw = [v.X for v in x]
    projected_action = [int(round(value)) for value in raw]
    lhs_values = [
        sum(raw),
        raw[0] + raw[3],
        raw[1] + raw[4],
        raw[2] + raw[5],
        raw[0] + raw[3]
    ]
    violations = [
        abs(lhs_values[0] - 3),
        max(0.0, 1 - lhs_values[1]),
        max(0.0, 1 - lhs_values[2]),
        max(0.0, 1 - lhs_values[3]),
        max(0.0, 1 - lhs_values[4])
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in raw)
    objective = model.ObjVal if math.isfinite(model.ObjVal) else None
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