import gurobipy as gp
import json
import math

model = gp.Model("SWOR074_patched")
model.Params.OutputFlag = 0

x = model.addVars(6, vtype=gp.GRB.BINARY, lb=0, ub=1, name="x")
benefit = [1014, 953, 911, 850, 789, 747]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x[i] for i in range(6)) <= 3, name="max_enabled_units")
model.addConstr(4*x[0] + x[1] + 2*x[2] + 3*x[3] + 4*x[4] + x[5] <= 7, name="grid_resource_capacity")
model.addConstr(x[0] + x[3] >= 1, name="min_clean_capability")
model.addConstr(x[1] + x[4] >= 1, name="min_backup_capability")
model.addConstr(x[1] + x[4] + x[5] == 1, name="exclusive_choice_B_E_F")
model.addConstr(x[0] + x[1] - x[4] - x[5] <= 1, name="ldr_untreated_land_disposal")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(x[i].X) for i in range(6)]
    projected_action = [int(round(v)) for v in values]
    checks = [
        (sum(values), "<=", 3.0),
        (4*values[0] + values[1] + 2*values[2] + 3*values[3] + 4*values[4] + values[5], "<=", 7.0),
        (values[0] + values[3], ">=", 1.0),
        (values[1] + values[4], ">=", 1.0),
        (values[1] + values[4] + values[5], "==", 1.0),
        (values[0] + values[1] - values[4] - values[5], "<=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in values)
    objective = float(model.ObjVal)
else:
    objective = None
    projected_action = []
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
