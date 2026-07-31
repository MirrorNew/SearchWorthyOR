import gurobipy as gp
import json
import math

model = gp.Model("SWOR081_patched")
model.Params.OutputFlag = 0

semantic_names = ["服务单元A", "服务单元B", "服务单元C", "服务单元D", "服务单元E", "服务单元F", "服务单元G", "服务单元H"]
benefits = [1017, 956, 895, 853, 792, 750, 689, 647]
clinical_resource_usage = [4, 1, 2, 3, 4, 1, 2, 3]
business_attributes = ["基础类别", "基础类别", "基础类别", "基础类别", "基础类别", "基础类别", "保障类别1", "保障类别2"]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
model.update()

model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="enabled_count_eq")
model.addConstr(x[0] + x[1] >= 1, name="emergency_coverage")
model.addConstr(x[1] + x[2] >= 1, name="continuity_coverage")
model.addConstr(x[0] + x[2] >= 1, name="specialty_coverage")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_minimum")
model.addConstr(x[0] + x[1] <= 1, name="policy_ab_mutex")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
    gp.GRB.SUBOPTIMAL: "SUBOPTIMAL"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)
    if abs(objective - round(objective)) <= 1e-9:
        objective = int(round(objective))

    checks = [
        ("==", sum(values), 3.0),
        (">=", values[0] + values[1], 1.0),
        (">=", values[1] + values[2], 1.0),
        (">=", values[0] + values[2], 1.0),
        (">=", values[0] + values[1] + values[2], 2.0),
        ("<=", values[0] + values[1], 1.0)
    ]
    violations = []
    for sense, lhs, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
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
