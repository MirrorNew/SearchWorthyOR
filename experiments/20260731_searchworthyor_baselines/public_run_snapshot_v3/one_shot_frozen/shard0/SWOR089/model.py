import gurobipy as gp
import json
import math

model = gp.Model("SWOR089_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
profits = [1004, 962, 901, 859, 798, 737, 695]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]

model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="frozen_exactly_three")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="early_supply_min_one")
model.addConstr(x[1] + x[2] + x[4] >= 1, name="late_supply_min_one")
model.addConstr(x[5] + x[6] >= 1, name="safeguard_option_min_one")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    integrality_violation = max(abs(value - round(value)) for value in values)
    rows = [
        (sum(values), "==", 3.0),
        (values[0] + values[1] + values[3] + values[6], ">=", 1.0),
        (values[1] + values[2] + values[4], ">=", 1.0),
        (values[5] + values[6], ">=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in rows:
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
        "projected_action": None,
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))