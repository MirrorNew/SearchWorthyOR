import gurobipy as gp
import json
import math

m = gp.Model("SWOR083_patched")
m.Params.OutputFlag = 0

x = [m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

m.setObjective(
    1012 * x[0] + 951 * x[1] + 909 * x[2] + 848 * x[3]
    + 806 * x[4] + 745 * x[5] + 684 * x[6],
    gp.GRB.MAXIMIZE,
)

m.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
m.addConstr(x[0] + x[3] + x[6] >= 1, name="cover_period_1")
m.addConstr(x[1] + x[4] >= 1, name="cover_period_2")
m.addConstr(x[2] + x[5] >= 1, name="cover_period_3")
m.addConstr(x[0] + x[3] >= 1, name="core_A_or_backup_D")
m.addConstr(x[0] + x[1] <= 1, name="policy_A_B_mutual_exclusion")

m.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(m.Status, str(m.Status))

if m.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in values]
    objective = float(m.ObjVal)
    checks = [
        ("==", sum(values), 3.0),
        (">=", values[0] + values[3] + values[6], 1.0),
        (">=", values[1] + values[4], 1.0),
        (">=", values[2] + values[5], 1.0),
        (">=", values[0] + values[3], 1.0),
        ("<=", values[0] + values[1], 1.0),
    ]
    violations = []
    for sense, lhs, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in values)
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
    "integrality_violation": integrality_violation,
}, ensure_ascii=False))