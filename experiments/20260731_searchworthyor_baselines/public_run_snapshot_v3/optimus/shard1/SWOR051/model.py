import gurobipy as gp
import json
import math

model = gp.Model("SWOR051_patched")
model.Params.OutputFlag = 0

# VARIABLES
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

# OBJECTIVE
benefit = [1004, 962, 901, 859, 798, 737]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

# BASE_CONSTRAINTS
model.addConstr(gp.quicksum(x) <= 3, name="max_enabled_modules")
model.addConstr(x[0] + x[3] >= 1, name="zone_1_coverage")
model.addConstr(x[1] + x[4] >= 1, name="zone_2_coverage")
model.addConstr(x[2] + x[5] >= 1, name="zone_3_coverage")
model.addConstr(-x[0] + x[1] + x[4] >= 0, name="access_requires_backhaul")
model.addConstr(x[0] + x[3] >= 1, name="core_or_backup")

# EXTERNAL_RULE_DOC_16E26A69821F91A1
model.addConstr(x[0] + x[1] <= 1, name="external_A_B_incompatibility")

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
    raw = [x[i].X for i in range(6)]
    projected_action = [int(v >= 0.5) for v in raw]
    integrality_violation = max(abs(v - round(v)) for v in raw)
    lhs_rows = [
        (sum(raw), "<=", 3),
        (raw[0] + raw[3], ">=", 1),
        (raw[1] + raw[4], ">=", 1),
        (raw[2] + raw[5], ">=", 1),
        (-raw[0] + raw[1] + raw[4], ">=", 0),
        (raw[0] + raw[3], ">=", 1),
        (raw[0] + raw[1], "<=", 1)
    ]
    violations = []
    for lhs, sense, rhs in lhs_rows:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    for value in raw:
        violations.append(max(0.0, -value, value - 1.0))
    max_constraint_violation = max(violations)
    objective = model.ObjVal
else:
    projected_action = [0, 0, 0, 0, 0, 0]
    integrality_violation = None
    max_constraint_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
