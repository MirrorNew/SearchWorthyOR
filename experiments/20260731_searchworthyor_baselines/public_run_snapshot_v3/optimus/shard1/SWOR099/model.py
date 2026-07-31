import gurobipy as gp
import json
import math

model = gp.Model("SWOR099_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}") for i in range(8)]
model.update()

benefit = [1015, 954, 912, 851, 790, 748, 687, 645]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

constraints = {}
constraints["c_required_count"] = model.addConstr(gp.quicksum(x) == 3, name="c_required_count")
constraints["c_early_plan"] = model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="c_early_plan")
constraints["c_late_plan"] = model.addConstr(x[1] + x[2] + x[4] + x[7] >= 1, name="c_late_plan")
constraints["c_exclusive_choice"] = model.addConstr(x[1] + x[4] + x[7] == 1, name="c_exclusive_choice")
constraints["c_fruit_or_vegetable"] = model.addConstr(x[6] + x[7] >= 1, name="c_fruit_or_vegetable")

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
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)
    integrality_violation = max(abs(value - round(value)) for value in values)

    checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[1] + values[3] + values[6], ">=", 1.0),
        (values[1] + values[2] + values[4] + values[7], ">=", 1.0),
        (values[1] + values[4] + values[7], "==", 1.0),
        (values[6] + values[7], ">=", 1.0)
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
