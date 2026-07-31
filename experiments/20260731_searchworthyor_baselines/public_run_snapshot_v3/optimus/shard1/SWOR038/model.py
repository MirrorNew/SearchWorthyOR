import gurobipy as gp
import json

model = gp.Model("SWOR038_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

benefit = [1011, 950, 908, 847, 805, 744]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) <= 3, name="maximum_enabled_modules")
model.addConstr(x[0] + x[3] >= 1, name="zone_1_coverage")
model.addConstr(x[1] + x[4] >= 1, name="zone_2_coverage")
model.addConstr(x[2] + x[5] >= 1, name="zone_3_coverage")
model.addConstr(x[0] - x[1] - x[4] <= 0, name="module_A_requires_backhaul")
model.addConstr(x[1] + x[4] + x[5] == 1, name="exactly_one_B_E_F")
model.addConstr(x[0] <= 0, name="policy_meal_period_A")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [x[i].X for i in range(6)]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)

    checks = [
        ("<=", sum(values), 3.0),
        (">=", values[0] + values[3], 1.0),
        (">=", values[1] + values[4], 1.0),
        (">=", values[2] + values[5], 1.0),
        ("<=", values[0] - values[1] - values[4], 0.0),
        ("==", values[1] + values[4] + values[5], 1.0),
        ("<=", values[0], 0.0)
    ]
    violations = []
    for sense, lhs, rhs in checks:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    objective = None
    projected_action = [0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))