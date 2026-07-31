import gurobipy as gp
import json
import math

# [VARIABLES]
model = gp.Model("SWOR086_patched")
model.Params.OutputFlag = 0
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

# [OBJECTIVE]
utilities = [1002, 960, 899, 857, 796, 735, 693]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# [C_EXACTLY_3]
model.addConstr(gp.quicksum(x) == 3, name="exactly_three_assignments")
# [C_SUBJECT_1]
model.addConstr(x[0] + x[3] + x[6] <= 1, name="resource_subject_1_at_most_one")
# [C_SUBJECT_2]
model.addConstr(x[1] + x[4] <= 1, name="resource_subject_2_at_most_one")
# [C_SUBJECT_3]
model.addConstr(x[2] + x[5] <= 1, name="resource_subject_3_at_most_one")
# [C_CORE]
model.addConstr(x[0] + x[1] + x[2] >= 2, name="at_least_two_core_candidates")
# [C_POLICY_GUARANTEE]
model.addConstr(x[5] + x[6] >= 1, name="policy_at_least_one_guarantee_option")

# [SOLVE_AND_REPORT]
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
    values = [float(v.X) for v in x]
    projected_action = [int(v >= 0.5) for v in values]
    checks = [
        ("==", sum(values), 3.0),
        ("<=", values[0] + values[3] + values[6], 1.0),
        ("<=", values[1] + values[4], 1.0),
        ("<=", values[2] + values[5], 1.0),
        (">=", values[0] + values[1] + values[2], 2.0),
        (">=", values[5] + values[6], 1.0)
    ]
    violations = []
    for sense, lhs, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in values)
    objective = float(model.ObjVal)
else:
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None
    objective = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))
