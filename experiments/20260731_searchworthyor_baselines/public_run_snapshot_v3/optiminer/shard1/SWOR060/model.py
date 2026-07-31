import gurobipy as gp
import json
import math

model = gp.Model("SWOR060_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

model.setObjective(
    1011 * x[0] + 950 * x[1] + 908 * x[2] + 847 * x[3]
    + 805 * x[4] + 744 * x[5] + 683 * x[6],
    gp.GRB.MAXIMIZE,
)

model.addConstr(x[0] + x[3] + x[6] == 1, name="transport_chain_segment_1")
model.addConstr(x[1] + x[4] == 1, name="transport_chain_segment_2")
model.addConstr(x[2] + x[5] == 1, name="transport_chain_segment_3")
model.addConstr(x[1] + x[4] + x[6] == 1, name="core_backup_emergency_exactly_one")
model.addConstr(x[5] + x[6] >= 1, name="policy保障_minimum")

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
    values = [var.X for var in x]
    projected_action = [int(value >= 0.5) for value in values]
    integrality_violation = max(abs(value - round(value)) for value in values)

    checks = [
        (values[0] + values[3] + values[6], "==", 1.0),
        (values[1] + values[4], "==", 1.0),
        (values[2] + values[5], "==", 1.0),
        (values[1] + values[4] + values[6], "==", 1.0),
        (values[5] + values[6], ">=", 1.0),
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(rhs - lhs, 0.0))
        else:
            violations.append(max(lhs - rhs, 0.0))

    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
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

print(json.dumps(result, ensure_ascii=False))
