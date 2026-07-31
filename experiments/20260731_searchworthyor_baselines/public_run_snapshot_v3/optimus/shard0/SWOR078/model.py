import gurobipy as gp
import json

# VARIABLES
model = gp.Model("SWOR078_patched")
model.Params.OutputFlag = 0
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

# OBJECTIVE
utilities = [1017, 956, 895, 853, 792, 750]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

# C_MAX_ENABLED
model.addConstr(gp.quicksum(x) <= 3, name="max_enabled_modules")
# C_ZONE_1
model.addConstr(x[0] + x[3] >= 1, name="zone_1_coverage")
# C_ZONE_2
model.addConstr(x[1] + x[4] >= 1, name="zone_2_coverage")
# C_ZONE_3
model.addConstr(x[2] + x[5] >= 1, name="zone_3_coverage")
# C_ACCESS_BACKHAUL
model.addConstr(-x[0] + x[1] + x[4] >= 0, name="main_access_backhaul")
# C_BACKUP_MUTEX
model.addConstr(x[4] + x[5] <= 1, name="backup_mutual_exclusion")
# POLICY_C_SAFEGUARD_MIN
model.addConstr(x[4] + x[5] >= 1, name="policy_minimum_safeguard")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

# SOLUTION_REPORT
if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in values]
    checks = [
        (sum(values), "<=", 3.0),
        (values[0] + values[3], ">=", 1.0),
        (values[1] + values[4], ">=", 1.0),
        (values[2] + values[5], ">=", 1.0),
        (-values[0] + values[1] + values[4], ">=", 0.0),
        (values[4] + values[5], "<=", 1.0),
        (values[4] + values[5], ">=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in values)
    objective = float(model.ObjVal)
else:
    projected_action = [0, 0, 0, 0, 0, 0]
    objective = None
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))