import gurobipy as gp
from gurobipy import GRB
import json
import math

model = gp.Model("SWOR010")
model.ModelSense = GRB.MAXIMIZE

x = [model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
model.setObjective(1000*x[0] + 958*x[1] + 897*x[2] + 855*x[3] + 794*x[4] + 752*x[5])

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_three")
model.addConstr(x[0] + x[1] + x[3] >= 1, name="front_segment_availability")
model.addConstr(x[1] + x[2] + x[4] >= 1, name="back_segment_frozen_requirement")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_candidates_minimum_two")

model.optimize()

if model.Status == GRB.OPTIMAL:
    values = [v.X for v in x]
    projected_action = [int(round(v)) for v in values]
    lhs_values = [
        sum(values),
        values[0] + values[1] + values[3],
        values[1] + values[2] + values[4],
        values[0] + values[1] + values[2]
    ]
    violations = [
        abs(lhs_values[0] - 3),
        max(0.0, 1 - lhs_values[1]),
        max(0.0, 1 - lhs_values[2]),
        max(0.0, 2 - lhs_values[3])
    ]
    result = {
        "status": "OPTIMAL",
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(v - round(v)) for v in values)
    }
else:
    result = {
        "status": str(model.Status),
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))