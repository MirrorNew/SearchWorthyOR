import gurobipy as gp
import json
import math

model = gp.Model("SWOR035_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
benefit = [1017, 956, 895, 853, 792, 750, 689]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_three")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="front_stage_minimum")
model.addConstr(x[1] + x[2] + x[4] >= 1, name="back_stage_minimum")
model.addConstr(x[0] + x[3] >= 1, name="core_or_backup_minimum")
model.addConstr(x[1] == 0, name="ban_irreversibly_unlabeled_retail")
model.addConstr(x[5] + x[6] - x[0] >= 0, name="matching_label_service_for_package_A")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))
objective = None
projected_action = None
max_constraint_violation = None
integrality_violation = None

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    raw_objective = float(model.ObjVal)
    objective = raw_objective if math.isfinite(raw_objective) else None
    checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[1] + values[3] + values[6], ">=", 1.0),
        (values[1] + values[2] + values[4], ">=", 1.0),
        (values[0] + values[3], ">=", 1.0),
        (values[1], "==", 0.0),
        (-values[0] + values[5] + values[6], ">=", 0.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))