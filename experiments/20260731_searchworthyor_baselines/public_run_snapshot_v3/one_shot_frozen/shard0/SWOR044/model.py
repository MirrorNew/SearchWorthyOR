import gurobipy
import json
import math

model = gurobipy.Model("SWOR044_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}") for i in range(7)]
model.setObjective(
    1008 * x[0] + 947 * x[1] + 905 * x[2] + 844 * x[3]
    + 802 * x[4] + 741 * x[5] + 699 * x[6],
    gurobipy.GRB.MAXIMIZE,
)

model.addConstr(gurobipy.quicksum(x) == 3, name="c_exactly_3")
model.addConstr(x[0] + x[3] + x[6] <= 1, name="c_subject1_at_most_1")
model.addConstr(x[1] + x[4] <= 1, name="c_subject2_at_most_1")
model.addConstr(x[2] + x[5] <= 1, name="c_subject3_at_most_1")
model.addConstr(x[1] + x[4] + x[6] == 1, name="c_core_backup_emergency_exactly_1")
model.addConstr(x[0] + x[1] <= 1, name="c_policy_A_B_not_joint")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    integrality_violation = max(abs(value - round(value)) for value in values)

    checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[3] + values[6], "<=", 1.0),
        (values[1] + values[4], "<=", 1.0),
        (values[2] + values[5], "<=", 1.0),
        (values[1] + values[4] + values[6], "==", 1.0),
        (values[0] + values[1], "<=", 1.0),
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))

    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": float(max(violations)),
        "integrality_violation": float(integrality_violation),
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": None,
        "max_constraint_violation": None,
        "integrality_violation": None,
    }

print(json.dumps(result, ensure_ascii=False))