import gurobipy
import json
import math

model = gurobipy.Model("SWOR007_base")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

# SLOT_OBJECTIVE
benefits = [1013, 952, 910, 849, 788, 746]
model.setObjective(gurobipy.quicksum(benefits[i] * x[i] for i in range(6)), gurobipy.GRB.MAXIMIZE)

# SLOT_SEGMENT_1
model.addConstr(x[0] + x[3] == 1, name="segment_1_exactly_one")
# SLOT_SEGMENT_2
model.addConstr(x[1] + x[4] == 1, name="segment_2_exactly_one")
# SLOT_SEGMENT_3
model.addConstr(x[2] + x[5] == 1, name="segment_3_exactly_one")
# SLOT_CORE_BACKUP
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_backup_D")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
    gurobipy.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [v.X for v in x]
    projected_action = [int(round(value)) for value in values]
    violations = [
        abs(values[0] + values[3] - 1),
        abs(values[1] + values[4] - 1),
        abs(values[2] + values[5] - 1),
        max(0.0, 1 - values[0] - values[3])
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
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
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
