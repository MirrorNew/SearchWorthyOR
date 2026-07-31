import gurobipy
import json
import math

model = gurobipy.Model("SWOR081")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
benefits = [1017, 956, 895, 853, 792, 750, 689, 647]
model.setObjective(gurobipy.quicksum(benefits[i] * x[i] for i in range(8)), gurobipy.GRB.MAXIMIZE)

model.addConstr(gurobipy.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[1] >= 1, name="emergency_A_or_B")
model.addConstr(x[1] + x[2] >= 1, name="continuity_B_or_C")
model.addConstr(x[0] + x[2] >= 1, name="specialty_A_or_C")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_ABC_at_least_2")

model.optimize()

if model.SolCount > 0:
    values = [x[i].X for i in range(8)]
    projected_action = [int(round(value)) for value in values]
    violations = [
        abs(sum(values) - 3),
        max(0.0, 1 - (values[0] + values[1])),
        max(0.0, 1 - (values[1] + values[2])),
        max(0.0, 1 - (values[0] + values[2])),
        max(0.0, 2 - (values[0] + values[1] + values[2]))
    ]
    integrality_violation = max(abs(value - round(value)) for value in values)
    result = {
        "status": "OPTIMAL" if model.Status == gurobipy.GRB.OPTIMAL else str(model.Status),
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": str(model.Status),
        "objective": None,
        "projected_action": [0, 0, 0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))