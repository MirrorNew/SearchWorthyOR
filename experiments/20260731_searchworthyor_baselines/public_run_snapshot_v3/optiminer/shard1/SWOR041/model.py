import gurobipy as gp
import json
import math

m = gp.Model("SWOR041_patched")
m.Params.OutputFlag = 0

x = [m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
utilities = [1000, 958, 897, 855, 794, 752, 691]
m.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

m.addConstr(gp.quicksum(x) == 3, name="select_exactly_three")
m.addConstr(x[0] + x[1] >= 1, name="emergency_coverage")
m.addConstr(x[1] + x[2] >= 1, name="continuity_coverage")
m.addConstr(x[0] + x[2] >= 1, name="specialty_coverage")
m.addConstr(x[5] + x[6] <= 1, name="terminal_backup_mutex")
m.addConstr(x[0] == 0, name="policy_A_ineligible")

m.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(m.Status, str(m.Status))

if m.SolCount > 0:
    values = [x[i].X for i in range(7)]
    projected_action = [int(round(v)) for v in values]
    checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[1], ">=", 1.0),
        (values[1] + values[2], ">=", 1.0),
        (values[0] + values[2], ">=", 1.0),
        (values[5] + values[6], "<=", 1.0),
        (values[0], "==", 0.0)
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
    integrality_violation = max(abs(v - round(v)) for v in values)
    objective = float(m.ObjVal)
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
