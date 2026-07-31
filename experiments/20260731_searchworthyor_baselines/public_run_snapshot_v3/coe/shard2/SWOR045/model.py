import gurobipy as gp
import json
import math

PROFIT = [1009, 948, 906, 845, 803, 742, 700]
ACTION_PROJECTION = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]

model = gp.Model("SWOR045_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = model.addVars(7, vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name="x")
model.setObjective(
    gp.quicksum(PROFIT[i] * x[i] for i in range(7)),
    gp.GRB.MAXIMIZE,
)

model.addConstr(gp.quicksum(x[i] for i in range(7)) == 3, name="build_exactly_3")
model.addConstr(x[0] + x[2] + x[4] + x[6] >= 1, name="cover_service_area_1")
model.addConstr(x[1] + x[3] + x[5] >= 1, name="cover_service_area_2")
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_D")
model.addConstr(x[0] + x[1] <= 1, name="policy_A_excludes_B")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))
objective = None
projected_action = [0, 0, 0, 0, 0, 0, 0]
max_constraint_violation = None
integrality_violation = None

if model.SolCount > 0:
    values = [x[i].X for i in range(7)]
    projected_action = [int(value >= 0.5) for value in values]
    objective = float(model.ObjVal)

    checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[2] + values[4] + values[6], ">=", 1.0),
        (values[1] + values[3] + values[5], ">=", 1.0),
        (values[0] + values[3], ">=", 1.0),
        (values[0] + values[1], "<=", 1.0),
    ]

    violations = []
    for lhs, sense, rhs in checks:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(math.fabs(lhs - rhs))

    max_constraint_violation = max(violations)
    integrality_violation = max(
        math.fabs(value - round(value)) for value in values
    )

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))