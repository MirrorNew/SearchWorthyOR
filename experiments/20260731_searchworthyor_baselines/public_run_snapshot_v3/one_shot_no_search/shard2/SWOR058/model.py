import gurobipy
import json
import math

model = gurobipy.Model("SWOR058")
model.Params.OutputFlag = 0

x = [
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}")
    for i in range(6)
]
model.update()

objective_coefficients = [1001, 959, 898, 856, 795, 753]
model.setObjective(
    gurobipy.quicksum(objective_coefficients[i] * x[i] for i in range(6)),
    gurobipy.GRB.MAXIMIZE,
)

model.addConstr(x[0] + x[3] == 1, name="transport_chain_segment_1_exactly_one")
model.addConstr(x[1] + x[4] == 1, name="transport_chain_segment_2_exactly_one")
model.addConstr(x[2] + x[5] == 1, name="transport_chain_segment_3_exactly_one")
model.addConstr(x[1] + x[4] + x[5] == 1, name="core_backup_emergency_exactly_one")

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
    raw_values = [var.X for var in x]
    projected_action = [int(round(value)) for value in raw_values]
    objective = float(model.ObjVal)

    constraint_residuals = [
        raw_values[0] + raw_values[3] - 1.0,
        raw_values[1] + raw_values[4] - 1.0,
        raw_values[2] + raw_values[5] - 1.0,
        raw_values[1] + raw_values[4] + raw_values[5] - 1.0,
    ]
    max_constraint_violation = max(abs(value) for value in constraint_residuals)
    integrality_violation = max(
        abs(value - round(value)) for value in raw_values
    )
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
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
