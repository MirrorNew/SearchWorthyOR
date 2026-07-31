import gurobipy as gp
import json
import math

model = gp.Model("SWOR045")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
model.update()

benefits = [1009, 948, 906, 845, 803, 742, 700]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x[i] for i in range(7)) == 3, name="build_exactly_three")
model.addConstr(x[0] + x[2] + x[4] + x[6] >= 1, name="service_area_1_coverage")
model.addConstr(x[1] + x[3] + x[5] >= 1, name="service_area_2_coverage")
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_backup_D")

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
    raw_values = [float(x[i].X) for i in range(7)]
    projected_action = [int(round(v)) for v in raw_values]
    objective = float(model.ObjVal)

    checks = [
        ("==", 3.0, sum(raw_values)),
        (">=", 1.0, raw_values[0] + raw_values[2] + raw_values[4] + raw_values[6]),
        (">=", 1.0, raw_values[1] + raw_values[3] + raw_values[5]),
        (">=", 1.0, raw_values[0] + raw_values[3])
    ]
    violations = []
    for sense, rhs, lhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in raw_values)
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0]
    objective = None
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
