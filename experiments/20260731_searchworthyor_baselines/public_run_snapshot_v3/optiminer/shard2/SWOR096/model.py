import gurobipy as gp
import json

model = gp.Model("SWOR096_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

revenues = [1016, 955, 894, 852, 791, 749, 688, 646]
model.setObjective(gp.quicksum(revenues[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="c_exactly_three_shifts")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="c_period_1_coverage")
model.addConstr(x[1] + x[4] + x[7] >= 1, name="c_period_2_coverage")
model.addConstr(x[2] + x[5] >= 1, name="c_period_3_coverage")
model.addConstr(x[6] + x[7] <= 1, name="c_backup_mutex")
model.addConstr(x[6] + x[7] >= 1, name="c_policy_guarantee_min")

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
    values = [x[i].X for i in range(8)]
    projected_action = [int(round(value)) for value in values]

    checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[3] + values[6], ">=", 1.0),
        (values[1] + values[4] + values[7], ">=", 1.0),
        (values[2] + values[5], ">=", 1.0),
        (values[6] + values[7], "<=", 1.0),
        (values[6] + values[7], ">=", 1.0)
    ]

    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))

    output = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(value - round(value)) for value in values)
    }
else:
    output = {
        "status": status,
        "objective": None,
        "projected_action": None,
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(output, ensure_ascii=False))
