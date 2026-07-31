import gurobipy as gp
import json

model = gp.Model("SWOR061_patched")
model.Params.OutputFlag = 0

# [VARIABLES]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

profits = [1017, 956, 895, 853, 792, 750, 689, 647]
capacities = [1, 2, 3, 4, 1, 2, 3, 4]

# [OBJECTIVE]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

# [BASE_MAX_MODES]
model.addConstr(gp.quicksum(x[i] for i in range(8)) <= 3, name="max_enabled_modes")

# [BASE_CAPACITY]
model.addConstr(gp.quicksum(capacities[i] * x[i] for i in range(8)) <= 6, name="equipment_capacity")

# [EVIDENCE_ELIGIBILITY]
model.addConstr(x[0] == 0, name="eligibility_mode_A")

# [SOLVE_AND_REPORT]
model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw = [float(var.X) for var in x]
    projected = [int(round(value)) for value in raw]
    mode_lhs = sum(raw)
    capacity_lhs = sum(capacities[i] * raw[i] for i in range(8))
    max_constraint_violation = max(
        0.0,
        mode_lhs - 3.0,
        capacity_lhs - 6.0,
        abs(raw[0])
    )
    integrality_violation = max(abs(value - round(value)) for value in raw)
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected,
        "max_constraint_violation": float(max_constraint_violation),
        "integrality_violation": float(integrality_violation)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": None,
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, sort_keys=True))
