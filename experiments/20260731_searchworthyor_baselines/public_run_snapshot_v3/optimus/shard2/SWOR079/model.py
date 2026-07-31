import gurobipy as gp
import json
import math

model = gp.Model("SWOR079_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
model.update()

benefit = [1010, 949, 907, 846, 804, 743]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) <= 3, name="maximum_enabled_modules")
model.addConstr(x[0] + x[3] >= 1, name="communication_zone_1")
model.addConstr(x[1] + x[4] >= 1, name="communication_zone_2")
model.addConstr(x[2] + x[5] >= 1, name="communication_zone_3")
model.addConstr(x[0] - x[1] - x[4] <= 0, name="module_A_backhaul_dependency")
model.addConstr(x[4] + x[5] >= 1, name="minimum_guarantee_compatible_modules")

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
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    integrality_violation = max(abs(value - round(value)) for value in values)

    checks = [
        (sum(values), "<=", 3),
        (values[0] + values[3], ">=", 1),
        (values[1] + values[4], ">=", 1),
        (values[2] + values[5], ">=", 1),
        (values[0] - values[1] - values[4], "<=", 0),
        (values[4] + values[5], ">=", 1)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))

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
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))
