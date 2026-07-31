import gurobipy as gp
import json
import math

# DATA_VARIABLES_OBJECTIVE
model = gp.Model("SWOR002_patched")
model.Params.OutputFlag = 0
benefits = [1008, 947, 905, 844, 802, 741, 699]
x = model.addVars(7, vtype=gp.GRB.BINARY, lb=0, ub=1, name="x")
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# BASE_C_COUNT
model.addConstr(gp.quicksum(x[i] for i in range(7)) <= 3, name="c_count_limit")
# BASE_C_ZONE_1
model.addConstr(x[0] + x[3] + x[6] >= 1, name="c_zone_1")
# BASE_C_ZONE_2
model.addConstr(x[1] + x[4] >= 1, name="c_zone_2")
# BASE_C_ZONE_3
model.addConstr(x[2] + x[5] >= 1, name="c_zone_3")
# BASE_C_ACCESS_BACKHAUL
model.addConstr(x[0] - x[1] - x[4] <= 0, name="c_access_backhaul")
# BASE_C_BACKUP_MUTEX
model.addConstr(x[5] + x[6] <= 1, name="c_backup_mutex")
# POLICY_C_GUARANTEE_BEGIN: DOC-A04EDF46B55C6C0B
model.addConstr(x[5] + x[6] >= 1, name="c_policy_guarantee")
# POLICY_C_GUARANTEE_END

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

# SOLUTION_VALIDATION_AND_OUTPUT
if model.SolCount > 0:
    values = [x[i].X for i in range(7)]
    projected_action = [int(round(value)) for value in values]
    evaluations = [
        ("<=", sum(values), 3.0),
        (">=", values[0] + values[3] + values[6], 1.0),
        (">=", values[1] + values[4], 1.0),
        (">=", values[2] + values[5], 1.0),
        ("<=", values[0] - values[1] - values[4], 0.0),
        ("<=", values[5] + values[6], 1.0),
        (">=", values[5] + values[6], 1.0)
    ]
    violations = []
    for sense, lhs, rhs in evaluations:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal if math.isfinite(model.ObjVal) else None
else:
    objective = None
    projected_action = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
