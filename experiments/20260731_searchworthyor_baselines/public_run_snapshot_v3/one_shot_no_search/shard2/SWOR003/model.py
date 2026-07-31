import gurobipy as gp
from gurobipy import GRB
import json
import math

model = gp.Model("SWOR003")
model.Params.OutputFlag = 0

profits = [1001, 959, 898, 856, 795, 753, 692]
capacity = [1, 2, 3, 4, 1, 2, 3]
x = [model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(7)), GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) <= 3, name="max_enabled_modes")
model.addConstr(gp.quicksum(capacity[i] * x[i] for i in range(7)) <= 6, name="equipment_capacity")
model.addConstr(x[0] + x[3] >= 1, name="core_or_backup")

model.optimize()

status_names = {
    GRB.LOADED: "LOADED",
    GRB.OPTIMAL: "OPTIMAL",
    GRB.INFEASIBLE: "INFEASIBLE",
    GRB.INF_OR_UNBD: "INF_OR_UNBD",
    GRB.UNBOUNDED: "UNBOUNDED",
    GRB.CUTOFF: "CUTOFF",
    GRB.ITERATION_LIMIT: "ITERATION_LIMIT",
    GRB.NODE_LIMIT: "NODE_LIMIT",
    GRB.TIME_LIMIT: "TIME_LIMIT",
    GRB.SOLUTION_LIMIT: "SOLUTION_LIMIT",
    GRB.INTERRUPTED: "INTERRUPTED",
    GRB.NUMERIC: "NUMERIC",
    GRB.SUBOPTIMAL: "SUBOPTIMAL",
    GRB.INPROGRESS: "INPROGRESS",
    GRB.USER_OBJ_LIMIT: "USER_OBJ_LIMIT"
}

if model.SolCount > 0:
    raw = [v.X for v in x]
    projected_action = [int(round(value)) for value in raw]
    count_lhs = sum(raw)
    capacity_lhs = sum(capacity[i] * raw[i] for i in range(7))
    core_lhs = raw[0] + raw[3]
    max_constraint_violation = max(
        0.0,
        count_lhs - 3.0,
        capacity_lhs - 6.0,
        1.0 - core_lhs
    )
    integrality_violation = max(abs(value - round(value)) for value in raw)
    result = {
        "status": status_names.get(model.Status, str(model.Status)),
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max_constraint_violation,
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": status_names.get(model.Status, str(model.Status)),
        "objective": None,
        "projected_action": [0, 0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))
