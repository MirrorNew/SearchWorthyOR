import gurobipy as gp
import json
import math

model = gp.Model("SWOR005_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
model.update()

profits = [1003, 961, 900, 858, 797, 736, 694]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_three")
model.addConstr(x[0] + x[2] + x[4] + x[6] >= 1, name="service_area_1_coverage")
model.addConstr(x[1] + x[3] + x[5] >= 1, name="service_area_2_coverage")
model.addConstr(x[5] + x[6] <= 1, name="terminal_backup_conflict")
model.addConstr(x[5] + x[6] >= 1, name="policy_safeguard_min")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": None,
    "projected_action": [],
    "max_constraint_violation": None,
    "integrality_violation": None
}

if model.SolCount > 0:
    values = [var.X for var in x]
    result["objective"] = float(model.ObjVal)
    result["projected_action"] = [int(round(value)) for value in values]

    checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[2] + values[4] + values[6], ">=", 1.0),
        (values[1] + values[3] + values[5], ">=", 1.0),
        (values[5] + values[6], "<=", 1.0),
        (values[5] + values[6], ">=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))

    result["max_constraint_violation"] = float(max(violations, default=0.0))
    result["integrality_violation"] = float(max((abs(value - round(value)) for value in values), default=0.0))

print(json.dumps(result, ensure_ascii=False))