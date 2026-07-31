import gurobipy
import json
import math

model = gurobipy.Model("SWOR007_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
model.setObjective(
    1013 * x[0] + 952 * x[1] + 910 * x[2]
    + 849 * x[3] + 788 * x[4] + 746 * x[5],
    gurobipy.GRB.MAXIMIZE,
)

model.addConstr(x[0] + x[3] == 1, name="segment_1_exactly_one")
model.addConstr(x[1] + x[4] == 1, name="segment_2_exactly_one")
model.addConstr(x[2] + x[5] == 1, name="segment_3_exactly_one")
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_backup_D_at_least_one")
# PATCH_POLICY_GUARANTEE: DOC-BF6E926BF6A2AA47
model.addConstr(x[4] + x[5] >= 1, name="guarantee_option_at_least_one")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    row_violations = [
        abs(values[0] + values[3] - 1.0),
        abs(values[1] + values[4] - 1.0),
        abs(values[2] + values[5] - 1.0),
        max(0.0, 1.0 - values[0] - values[3]),
        max(0.0, 1.0 - values[4] - values[5]),
    ]
    bound_violations = [max(0.0, -value, value - 1.0) for value in values]
    max_constraint_violation = max(row_violations + bound_violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal)
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
    "integrality_violation": integrality_violation,
}, ensure_ascii=False))
