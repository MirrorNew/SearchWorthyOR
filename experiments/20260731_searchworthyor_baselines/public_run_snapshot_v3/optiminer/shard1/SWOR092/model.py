import gurobipy as gp
import json
import math

model = gp.Model("SWOR092_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

profits = [1000, 958, 897, 855, 794, 752, 691]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="cover_period_1")
model.addConstr(x[1] + x[4] >= 1, name="cover_period_2")
model.addConstr(x[2] + x[5] >= 1, name="cover_period_3")
model.addConstr(x[1] + x[4] + x[6] == 1, name="exactly_one_B_E_G")
model.addConstr(x[5] + x[6] >= 1, name="paid_rest_4h")

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
    projected_action = [int(round(v)) for v in raw]
    objective = float(model.ObjVal)

    checks = [
        (sum(raw), "==", 3.0),
        (raw[0] + raw[3] + raw[6], ">=", 1.0),
        (raw[1] + raw[4], ">=", 1.0),
        (raw[2] + raw[5], ">=", 1.0),
        (raw[1] + raw[4] + raw[6], "==", 1.0),
        (raw[5] + raw[6], ">=", 1.0)
    ]

    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))

    violations.extend(max(0.0, -v, v - 1.0) for v in raw)
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(v - round(v)) for v in raw)
else:
    objective = None
    projected_action = [0, 0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
