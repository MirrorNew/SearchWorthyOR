import gurobipy as gp
import json
import math

model = gp.Model("SWOR058_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
model.setObjective(
    1001 * x[0] + 959 * x[1] + 898 * x[2] +
    856 * x[3] + 795 * x[4] + 753 * x[5],
    gp.GRB.MAXIMIZE
)

model.addConstr(x[0] + x[3] == 1, name="chain_1_exactly_one")
model.addConstr(x[1] + x[4] == 1, name="chain_2_exactly_one")
model.addConstr(x[2] + x[5] == 1, name="chain_3_exactly_one")
model.addConstr(x[1] + x[4] + x[5] == 1, name="core_B_E_F_exactly_one")
model.addConstr(x[0] + x[1] <= 1, name="federal_minimum_rest_A_B_incompatibility")

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
    objective = model.ObjVal
    checks = [
        (values[0] + values[3], "==", 1),
        (values[1] + values[4], "==", 1),
        (values[2] + values[5], "==", 1),
        (values[1] + values[4] + values[5], "==", 1),
        (values[0] + values[1], "<=", 1)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    objective = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))
