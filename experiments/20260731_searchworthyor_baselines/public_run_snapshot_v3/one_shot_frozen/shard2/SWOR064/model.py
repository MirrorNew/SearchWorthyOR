import gurobipy as gp
import json
import math

model = gp.Model("SWOR064_patched")
model.Params.OutputFlag = 0

x = [
    model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}")
    for i in range(8)
]

profits = [1001, 959, 898, 856, 795, 753, 692, 631]
model.setObjective(
    gp.quicksum(profits[i] * x[i] for i in range(8)),
    gp.GRB.MAXIMIZE,
)

model.addConstr(gp.quicksum(x) == 3, name="facility_count")
model.addConstr(x[0] + x[2] + x[4] + x[6] >= 1, name="service_area_1_coverage")
model.addConstr(x[1] + x[3] + x[5] + x[7] >= 1, name="service_area_2_coverage")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_candidates_minimum")
model.addConstr(x[0] + x[1] <= 1, name="policy_no_joint_A_B")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
}
status = status_names.get(model.Status, f"STATUS_{model.Status}")

if model.SolCount > 0:
    raw_values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in raw_values]
    objective = float(model.ObjVal)

    rows = [
        ("==", 3.0, [1, 1, 1, 1, 1, 1, 1, 1]),
        (">=", 1.0, [1, 0, 1, 0, 1, 0, 1, 0]),
        (">=", 1.0, [0, 1, 0, 1, 0, 1, 0, 1]),
        (">=", 2.0, [1, 1, 1, 0, 0, 0, 0, 0]),
        ("<=", 1.0, [1, 1, 0, 0, 0, 0, 0, 0]),
    ]
    violations = []
    for sense, rhs, coefficients in rows:
        lhs = sum(coefficients[i] * raw_values[i] for i in range(8))
        if sense == "==":
            violations.append(math.fabs(lhs - rhs))
        elif sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))

    max_constraint_violation = max(violations)
    integrality_violation = max(
        math.fabs(value - round(value)) for value in raw_values
    )
else:
    objective = None
    projected_action = [0] * 8
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
