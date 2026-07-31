import gurobipy as gp
import json
import math

model = gp.Model("SWOR015_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

model.setObjective(
    1012 * x[0] + 951 * x[1] + 909 * x[2] +
    848 * x[3] + 806 * x[4] + 745 * x[5],
    gp.GRB.MAXIMIZE
)

model.addConstr(gp.quicksum(x) == 3, name="c_exactly_3")
model.addConstr(x[0] + x[1] + x[3] >= 1, name="c_front_supply")
model.addConstr(x[1] + x[2] + x[4] >= 1, name="c_late_supply")
model.addConstr(x[4] + x[5] <= 1, name="c_terminal_mutex")
model.addConstr(x[0] + x[1] <= 1, name="c_policy_A_implies_not_B")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw = [v.X for v in x]
    projected_action = [int(round(value)) for value in raw]
    integrality_violation = max(abs(value - round(value)) for value in raw)
    lhs_values = [
        sum(raw),
        raw[0] + raw[1] + raw[3],
        raw[1] + raw[2] + raw[4],
        raw[4] + raw[5],
        raw[0] + raw[1]
    ]
    violations = [
        abs(lhs_values[0] - 3),
        max(0.0, 1 - lhs_values[1]),
        max(0.0, 1 - lhs_values[2]),
        max(0.0, lhs_values[3] - 1),
        max(0.0, lhs_values[4] - 1)
    ]
    objective = model.ObjVal
    max_constraint_violation = max(violations)
else:
    projected_action = [0, 0, 0, 0, 0, 0]
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