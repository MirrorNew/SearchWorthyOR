import gurobipy as gp
import json
import math

model = gp.Model("SWOR079_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
model.setObjective(
    1010 * x[0] + 949 * x[1] + 907 * x[2] +
    846 * x[3] + 804 * x[4] + 743 * x[5],
    gp.GRB.MAXIMIZE
)

model.addConstr(gp.quicksum(x) <= 3, name="module_limit")
model.addConstr(x[0] + x[3] >= 1, name="communication_zone_1")
model.addConstr(x[1] + x[4] >= 1, name="communication_zone_2")
model.addConstr(x[2] + x[5] >= 1, name="communication_zone_3")
model.addConstr(x[0] - x[1] - x[4] <= 0, name="module_A_requires_B_or_E")
model.addConstr(x[4] + x[5] >= 1, name="policy_safeguard_option")

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
    values = [v.X for v in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)

    checks = [
        (sum(values), "<=", 3.0),
        (values[0] + values[3], ">=", 1.0),
        (values[1] + values[4], ">=", 1.0),
        (values[2] + values[5], ">=", 1.0),
        (values[0] - values[1] - values[4], "<=", 0.0),
        (values[4] + values[5], ">=", 1.0)
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
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    objective = None
    projected_action = [0, 0, 0, 0, 0, 0]
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