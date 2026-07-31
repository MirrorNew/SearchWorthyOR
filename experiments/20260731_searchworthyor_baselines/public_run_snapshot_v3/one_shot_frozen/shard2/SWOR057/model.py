import gurobipy
import json
import math

model = gurobipy.Model("SWOR057_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

model.setObjective(
    1008 * x[0] + 947 * x[1] + 905 * x[2] +
    844 * x[3] + 802 * x[4] + 741 * x[5],
    gurobipy.GRB.MAXIMIZE
)

model.addConstr(sum(x) == 3, name="c_exactly_three_shifts")
model.addConstr(x[0] + x[3] >= 1, name="c_period_1_coverage")
model.addConstr(x[1] + x[4] >= 1, name="c_period_2_coverage")
model.addConstr(x[2] + x[5] >= 1, name="c_period_3_coverage")
model.addConstr(x[4] + x[5] >= 1, name="c_policy_guarantee_option")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    objective = model.ObjVal
    constraint_violations = []
    for constr in model.getConstrs():
        lhs = model.getRow(constr).getValue()
        if constr.Sense == "<":
            violation = max(0.0, lhs - constr.RHS)
        elif constr.Sense == ">":
            violation = max(0.0, constr.RHS - lhs)
        else:
            violation = abs(lhs - constr.RHS)
        constraint_violations.append(violation)
    max_constraint_violation = max(constraint_violations) if constraint_violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    projected_action = []
    objective = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
