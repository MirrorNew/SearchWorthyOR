import gurobipy as gp
import json
import math

model = gp.Model("SWOR026_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
benefit = [1002, 960, 899, 857, 796, 735, 693]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) <= 3, name="maximum_enabled_modules")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="zone_1_coverage")
model.addConstr(x[1] + x[4] >= 1, name="zone_2_coverage")
model.addConstr(x[2] + x[5] >= 1, name="zone_3_coverage")
model.addConstr(x[0] - x[1] - x[4] <= 0, name="primary_access_requires_backhaul")
model.addConstr(x[1] + x[4] + x[6] == 1, name="exactly_one_B_E_G")
model.addConstr(x[0] + x[1] <= 1, name="policy_A_excludes_B")

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
    raw = [float(v.X) for v in x]
    projected = [int(round(value)) for value in raw]
    checks = [
        (sum(raw), "<=", 3.0),
        (raw[0] + raw[3] + raw[6], ">=", 1.0),
        (raw[1] + raw[4], ">=", 1.0),
        (raw[2] + raw[5], ">=", 1.0),
        (raw[0] - raw[1] - raw[4], "<=", 0.0),
        (raw[1] + raw[4] + raw[6], "==", 1.0),
        (raw[0] + raw[1], "<=", 1.0)
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
    integrality_violation = max(abs(value - round(value)) for value in raw)
    objective = float(model.ObjVal)
else:
    projected = []
    objective = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))