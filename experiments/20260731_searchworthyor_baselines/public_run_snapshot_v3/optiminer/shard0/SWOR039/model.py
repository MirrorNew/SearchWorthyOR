# -*- coding: utf-8 -*-
import gurobipy as gp
import json
import math

model = gp.Model("SWOR039_patched")
model.Params.OutputFlag = 0

# REGION VARIABLES
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
model.update()

# REGION OBJECTIVE
收益 = [1005, 963, 902, 841, 799, 738, 696]
model.setObjective(gp.quicksum(收益[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# REGION C_SEGMENT_1
model.addConstr(x[0] + x[3] + x[6] == 1, name="segment_1_exactly_one")

# REGION C_SEGMENT_2
model.addConstr(x[1] + x[4] == 1, name="segment_2_exactly_one")

# REGION C_SEGMENT_3
model.addConstr(x[2] + x[5] == 1, name="segment_3_exactly_one")

# REGION C_CORE_ABC
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_ABC_at_least_two")

# REGION C_POLICY_A_EXCLUDES_B
model.addConstr(x[0] + x[1] <= 1, name="policy_A_excludes_B")

# REGION SOLVE_AND_REPORT
model.optimize()

if model.Status == gp.GRB.OPTIMAL:
    status = "OPTIMAL"
elif model.Status == gp.GRB.INFEASIBLE:
    status = "INFEASIBLE"
elif model.Status == gp.GRB.INF_OR_UNBD:
    status = "INF_OR_UNBD"
elif model.Status == gp.GRB.UNBOUNDED:
    status = "UNBOUNDED"
elif model.Status == gp.GRB.TIME_LIMIT:
    status = "TIME_LIMIT"
else:
    status = str(model.Status)

if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in values]
    objective = float(model.ObjVal)
    checks = [
        (values[0] + values[3] + values[6], "==", 1.0),
        (values[1] + values[4], "==", 1.0),
        (values[2] + values[5], "==", 1.0),
        (values[0] + values[1] + values[2], ">=", 2.0),
        (values[0] + values[1], "<=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in values)
    if not math.isfinite(objective):
        objective = None
else:
    objective = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))