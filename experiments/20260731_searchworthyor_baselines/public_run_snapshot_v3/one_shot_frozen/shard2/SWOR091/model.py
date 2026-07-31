import gurobipy as gp
import json
import math

model = gp.Model("SWOR091_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0
model.Params.Threads = 1

# [VARS]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

# [OBJ]
benefit = [1014, 953, 911, 850, 789, 747]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

# [C_COUNT]
model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
# [C_PERIOD_1]
model.addConstr(x[0] + x[3] >= 1, name="cover_period_1")
# [C_PERIOD_2]
model.addConstr(x[1] + x[4] >= 1, name="cover_period_2")
# [C_PERIOD_3]
model.addConstr(x[2] + x[5] >= 1, name="cover_period_3")
# [C_CORE]
model.addConstr(x[0] + x[1] + x[2] >= 2, name="enable_at_least_2_core_shifts")
# [C_POLICY]
model.addConstr(x[0] + x[1] <= 1, name="policy_forbid_A_and_B_together")

# [SOLVE_AND_REPORT]
model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": None,
    "projected_action": [],
    "max_constraint_violation": None,
    "integrality_violation": None
}
if model.SolCount > 0:
    raw = [v.X for v in x]
    projected = [1 if value >= 0.5 else 0 for value in raw]
    checks = [
        (sum(raw), "==", 3.0),
        (raw[0] + raw[3], ">=", 1.0),
        (raw[1] + raw[4], ">=", 1.0),
        (raw[2] + raw[5], ">=", 1.0),
        (raw[0] + raw[1] + raw[2], ">=", 2.0),
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
    result["objective"] = model.ObjVal
    result["projected_action"] = projected
    result["max_constraint_violation"] = max(violations)
    result["integrality_violation"] = max(abs(value - round(value)) for value in raw)
print(json.dumps(result, ensure_ascii=False, sort_keys=True))