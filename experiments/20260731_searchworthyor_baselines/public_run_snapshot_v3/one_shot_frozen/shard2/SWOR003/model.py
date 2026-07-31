import gurobipy as gp
import json
import math

model = gp.Model("SWOR003_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
profits = [1001, 959, 898, 856, 795, 753, 692]
capacity = [1, 2, 3, 4, 1, 2, 3]

model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) <= 3, name="max_active_modes")
model.addConstr(gp.quicksum(capacity[i] * x[i] for i in range(7)) <= 6, name="equipment_capacity")
model.addConstr(x[0] + x[3] >= 1, name="core_or_backup")
model.addConstr(x[0] == 0, name="reg_menu_calorie_compliance_A")

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
    raw = [v.X for v in x]
    projected = [int(value >= 0.5) for value in raw]
    violations = [
        max(0.0, sum(raw) - 3.0),
        max(0.0, sum(capacity[i] * raw[i] for i in range(7)) - 6.0),
        max(0.0, 1.0 - raw[0] - raw[3]),
        abs(raw[0])
    ]
    integrality_violation = max(abs(value - round(value)) for value in raw)
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected,
        "max_constraint_violation": float(max(violations)),
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