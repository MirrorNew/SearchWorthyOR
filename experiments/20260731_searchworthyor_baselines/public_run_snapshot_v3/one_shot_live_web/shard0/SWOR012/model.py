import gurobipy
import json
import math

model = gurobipy.Model("SWOR012")
model.Params.OutputFlag = 0

x = [
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}")
    for i in range(6)
]

benefits = [1015, 954, 912, 851, 790, 748]
model.setObjective(
    gurobipy.quicksum(benefits[i] * x[i] for i in range(6)),
    gurobipy.GRB.MAXIMIZE,
)

model.addConstr(gurobipy.quicksum(x) == 3, name="select_exactly_three")
model.addConstr(x[0] + x[1] >= 1, name="emergency_coverage")
model.addConstr(x[1] + x[2] >= 1, name="continuity_coverage")
model.addConstr(x[0] + x[2] >= 1, name="specialty_coverage")
model.addConstr(x[0] + x[3] >= 1, name="core_candidate_or_backup")
model.addConstr(x[0] + x[1] <= 1, name="rcra_lqg_no_180_day_path")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
    gurobipy.GRB.INTERRUPTED: "INTERRUPTED",
}

result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": None,
    "projected_action": [0, 0, 0, 0, 0, 0],
    "max_constraint_violation": None,
    "integrality_violation": None,
}

if model.SolCount > 0:
    result["objective"] = float(model.ObjVal)
    result["projected_action"] = [int(round(v.X)) for v in x]
    result["max_constraint_violation"] = float(model.ConstrVio)
    result["integrality_violation"] = float(
        max(abs(v.X - round(v.X)) for v in x)
    )

print(json.dumps(result, ensure_ascii=False))