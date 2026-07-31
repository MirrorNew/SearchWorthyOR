import gurobipy as gp
import json
import math

model = gp.Model("SWOR044_patched")
model.Params.OutputFlag = 0
model.Params.Threads = 1
model.Params.MIPGap = 0.0

# VARIABLES_PUBLIC_TASK
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

# OBJECTIVE_PUBLIC_TASK
utilities = [1008, 947, 905, 844, 802, 741, 699]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# BASE_CONSTRAINT_ASSIGNMENT_COUNT
model.addConstr(gp.quicksum(x) == 3, name="required_assignment_count")
# BASE_CONSTRAINT_SUBJECT_1
model.addConstr(x[0] + x[3] + x[6] <= 1, name="resource_subject_1_at_most_one")
# BASE_CONSTRAINT_SUBJECT_2
model.addConstr(x[1] + x[4] <= 1, name="resource_subject_2_at_most_one")
# BASE_CONSTRAINT_SUBJECT_3
model.addConstr(x[2] + x[5] <= 1, name="resource_subject_3_at_most_one")
# BASE_CONSTRAINT_CORE_EXACT_ONE
model.addConstr(x[1] + x[4] + x[6] == 1, name="core_B_E_G_exactly_one")
# POLICY_CONSTRAINT_DOC_196C7F975A8A694A
model.addConstr(x[0] + x[1] <= 1, name="policy_A_B_not_together")

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

if model.SolCount > 0:
    values = [float(x[i].X) for i in range(7)]
    projected_action = [int(round(v)) for v in values]
    objective = float(model.ObjVal)
    if not math.isfinite(objective):
        objective = None

    checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[3] + values[6], "<=", 1.0),
        (values[1] + values[4], "<=", 1.0),
        (values[2] + values[5], "<=", 1.0),
        (values[1] + values[4] + values[6], "==", 1.0),
        (values[0] + values[1], "<=", 1.0)
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
    integrality_violation = max(min(abs(v), abs(1.0 - v)) for v in values)
else:
    objective = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))