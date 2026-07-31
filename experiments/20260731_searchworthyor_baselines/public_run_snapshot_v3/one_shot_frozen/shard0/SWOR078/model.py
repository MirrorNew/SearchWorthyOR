import gurobipy
import json
import math

# [MODEL_AND_VARIABLES]
model = gurobipy.Model("SWOR078_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0
x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

# [OBJECTIVE]
utility = [1017, 956, 895, 853, 792, 750]
model.setObjective(gurobipy.quicksum(utility[i] * x[i] for i in range(6)), gurobipy.GRB.MAXIMIZE)

# [BASE_MODULE_LIMIT]
model.addConstr(gurobipy.quicksum(x) <= 3, name="base_module_limit")
# [BASE_ZONE_1]
model.addConstr(x[0] + x[3] >= 1, name="base_zone_1_connectivity")
# [BASE_ZONE_2]
model.addConstr(x[1] + x[4] >= 1, name="base_zone_2_connectivity")
# [BASE_ZONE_3]
model.addConstr(x[2] + x[5] >= 1, name="base_zone_3_connectivity")
# [BASE_A_REQUIRES_B_OR_E]
model.addConstr(x[0] - x[1] - x[4] <= 0, name="base_A_requires_B_or_E")
# [BASE_E_F_MUTEX]
model.addConstr(x[4] + x[5] <= 1, name="base_E_F_mutual_exclusion")
# [POLICY_SAFEGUARD]
model.addConstr(x[4] + x[5] >= 1, name="policy_at_least_one_safeguard")

# [SOLVE_AND_REPORT]
model.optimize()
status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(value >= 0.5) for value in values]
    lhs_checks = [
        ("<=", sum(values), 3.0),
        (">=", values[0] + values[3], 1.0),
        (">=", values[1] + values[4], 1.0),
        (">=", values[2] + values[5], 1.0),
        ("<=", values[0] - values[1] - values[4], 0.0),
        ("<=", values[4] + values[5], 1.0),
        (">=", values[4] + values[5], 1.0)
    ]
    violations = []
    for sense, lhs, rhs in lhs_checks:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal if math.isfinite(model.ObjVal) else None
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
    "integrality_violation": integrality_violation
}, ensure_ascii=False))