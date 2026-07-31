import gurobipy as gp
import json
import math

model = gp.Model("SWOR055")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
model.setObjective(
    1013 * x[0] + 952 * x[1] + 910 * x[2] + 849 * x[3]
    + 788 * x[4] + 746 * x[5] + 685 * x[6],
    gp.GRB.MAXIMIZE,
)

model.addConstr(gp.quicksum(x) == 3, name="enable_exactly_three_service_units")
model.addConstr(x[0] + x[1] >= 1, name="emergency_coverage")
model.addConstr(x[1] + x[2] >= 1, name="continuity_of_care")
model.addConstr(x[0] + x[2] >= 1, name="specialty_service")
model.addConstr(x[1] + x[4] + x[6] == 1, name="exactly_one_of_B_E_G")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw = [var.X for var in x]
    projected = [int(round(value)) for value in raw]
    integrality_violation = max(abs(value - round(value)) for value in raw)

    checks = [
        (sum(raw), "==", 3.0),
        (raw[0] + raw[1], ">=", 1.0),
        (raw[1] + raw[2], ">=", 1.0),
        (raw[0] + raw[2], ">=", 1.0),
        (raw[1] + raw[4] + raw[6], "==", 1.0),
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))

    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected,
        "max_constraint_violation": max(violations),
        "integrality_violation": integrality_violation,
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None,
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))
