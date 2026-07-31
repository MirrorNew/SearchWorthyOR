import gurobipy as gp
import json
import math

model = gp.Model("SWOR091")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

model.setObjective(
    1014 * x[0] + 953 * x[1] + 911 * x[2] +
    850 * x[3] + 789 * x[4] + 747 * x[5],
    gp.GRB.MAXIMIZE
)

model.addConstr(gp.quicksum(x) == 3, name="exactly_three_shifts")
model.addConstr(x[0] + x[3] >= 1, name="period_1_coverage")
model.addConstr(x[1] + x[4] >= 1, name="period_2_coverage")
model.addConstr(x[2] + x[5] >= 1, name="period_3_coverage")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="at_least_two_core_shifts")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    integrality_violation = max(abs(value - round(value)) for value in values)

    checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[3], ">=", 1.0),
        (values[1] + values[4], ">=", 1.0),
        (values[2] + values[5], ">=", 1.0),
        (values[0] + values[1] + values[2], ">=", 2.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))

    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))