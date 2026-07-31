import gurobipy as gp
import json
import math

model = gp.Model("SWOR058_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

model.setObjective(
    1001 * x[0] + 959 * x[1] + 898 * x[2]
    + 856 * x[3] + 795 * x[4] + 753 * x[5],
    gp.GRB.MAXIMIZE
)

model.addConstr(x[0] + x[3] == 1, name="frozen_chain_1_exactly_one")
model.addConstr(x[1] + x[4] == 1, name="frozen_chain_2_exactly_one")
model.addConstr(x[2] + x[5] == 1, name="frozen_chain_3_exactly_one")
model.addConstr(x[1] + x[4] + x[5] == 1, name="frozen_core_backup_emergency_exactly_one")
model.addConstr(x[0] + x[1] <= 1, name="regulatory_minimum_10h_rest_A_B")

model.optimize()

status = "OPTIMAL" if model.Status == gp.GRB.OPTIMAL else str(model.Status)
if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    violations = [
        abs(values[0] + values[3] - 1.0),
        abs(values[1] + values[4] - 1.0),
        abs(values[2] + values[5] - 1.0),
        abs(values[1] + values[4] + values[5] - 1.0),
        max(0.0, values[0] + values[1] - 1.0)
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal)
else:
    projected_action = [0, 0, 0, 0, 0, 0]
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
print(json.dumps(result, ensure_ascii=False, allow_nan=False))