import gurobipy as gp
import json
import math

model = gp.Model("SWOR004_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

model.setObjective(
    1010 * x[0] + 949 * x[1] + 907 * x[2] + 846 * x[3]
    + 804 * x[4] + 743 * x[5] + 682 * x[6],
    gp.GRB.MAXIMIZE,
)

model.addConstr(gp.quicksum(x) == 3, name="c_frozen_exactly_three")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="c_front_segment")
model.addConstr(x[1] + x[2] + x[4] >= 1, name="c_back_segment")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="c_core_candidates")
model.addConstr(x[0] == 0, name="c_policy_A_ineligible")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    lhs_values = [
        sum(values),
        values[0] + values[1] + values[3] + values[6],
        values[1] + values[2] + values[4],
        values[0] + values[1] + values[2],
        values[0],
    ]
    violations = [
        abs(lhs_values[0] - 3),
        max(0.0, 1 - lhs_values[1]),
        max(0.0, 1 - lhs_values[2]),
        max(0.0, 2 - lhs_values[3]),
        abs(lhs_values[4]),
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0]
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
