import gurobipy as gp
import json
import math

model = gp.Model("SWOR096_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

revenues = [1016, 955, 894, 852, 791, 749, 688, 646]
model.setObjective(gp.quicksum(revenues[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="exactly_three_shift_blocks")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="period_1_coverage")
model.addConstr(x[1] + x[4] + x[7] >= 1, name="period_2_frozen_coverage")
model.addConstr(x[2] + x[5] >= 1, name="period_3_required_coverage")
model.addConstr(x[6] + x[7] <= 1, name="terminal_backup_mutual_exclusion")
model.addConstr(x[6] + x[7] >= 1, name="applicable_policy保障_minimum")

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
    values = [float(x[i].X) for i in range(8)]
    projected_action = [int(round(value)) for value in values]
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, 1.0 - (values[0] + values[3] + values[6])),
        max(0.0, 1.0 - (values[1] + values[4] + values[7])),
        max(0.0, 1.0 - (values[2] + values[5])),
        max(0.0, values[6] + values[7] - 1.0),
        max(0.0, 1.0 - (values[6] + values[7]))
    ]
    integrality_violation = max(abs(value - round(value)) for value in values)
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))