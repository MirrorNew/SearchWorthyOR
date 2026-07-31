# -*- coding: utf-8 -*-
import gurobipy as gp
import json
import math

model = gp.Model("SWOR046_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
model.setObjective(
    1007*x[0] + 965*x[1] + 904*x[2] + 843*x[3]
    + 801*x[4] + 740*x[5] + 698*x[6],
    gp.GRB.MAXIMIZE
)

model.addConstr(gp.quicksum(x) == 3, name="c_position_count")
model.addConstr(3*x[0] + 4*x[1] + x[2] + 2*x[3] + 3*x[4] + 4*x[5] + x[6] <= 12, name="c_capital_limit")
model.addConstr(3*x[0] + 5*x[1] + 2*x[2] + 4*x[3] + x[4] + 3*x[5] + 5*x[6] <= 15, name="c_risk_limit")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="c_core_minimum")
model.addConstr(x[0] + x[1] <= 1, name="c_policy_A_excludes_B")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.SUBOPTIMAL: "SUBOPTIMAL"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [v.X for v in x]
    projected_action = [int(round(v)) for v in values]
    lhs_values = [
        sum(values),
        3*values[0] + 4*values[1] + values[2] + 2*values[3] + 3*values[4] + 4*values[5] + values[6],
        3*values[0] + 5*values[1] + 2*values[2] + 4*values[3] + values[4] + 3*values[5] + 5*values[6],
        values[0] + values[1] + values[2],
        values[0] + values[1]
    ]
    violations = [
        abs(lhs_values[0] - 3),
        max(0.0, lhs_values[1] - 12),
        max(0.0, lhs_values[2] - 15),
        max(0.0, 2 - lhs_values[3]),
        max(0.0, lhs_values[4] - 1)
    ]
    bound_violations = [max(0.0, -v, v - 1.0) for v in values]
    integrality_violation = max(abs(v - round(v)) for v in values)
    max_constraint_violation = max(violations + bound_violations)
    objective = model.ObjVal if math.isfinite(model.ObjVal) else None
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