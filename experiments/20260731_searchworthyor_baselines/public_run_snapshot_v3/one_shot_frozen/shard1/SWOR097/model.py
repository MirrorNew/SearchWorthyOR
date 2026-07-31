import gurobipy as gp
import json
import math

model = gp.Model("SWOR097_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
utilities = [1012, 951, 909, 848, 806, 745, 684, 642]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]

# objective
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

# base constraints
model.addConstr(gp.quicksum(x) == 3, name="exactly_3_assignments")
model.addConstr(x[0] + x[3] + x[6] <= 1, name="subject_1_at_most_one")
model.addConstr(x[1] + x[4] + x[7] <= 1, name="subject_2_at_most_one")
model.addConstr(x[2] + x[5] <= 1, name="subject_3_at_most_one")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="at_least_two_core_matches")

# policy patch: DOC-72AE66B0846EAA3C
model.addConstr(x[0] + x[1] <= 1, name="policy_A_B_mutual_exclusion")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, "STATUS_" + str(model.Status))

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    integrality_violation = max(abs(value - round(value)) for value in values)

    constraint_data = [
        ("==", 3.0, [(i, 1.0) for i in range(8)]),
        ("<=", 1.0, [(0, 1.0), (3, 1.0), (6, 1.0)]),
        ("<=", 1.0, [(1, 1.0), (4, 1.0), (7, 1.0)]),
        ("<=", 1.0, [(2, 1.0), (5, 1.0)]),
        (">=", 2.0, [(0, 1.0), (1, 1.0), (2, 1.0)]),
        ("<=", 1.0, [(0, 1.0), (1, 1.0)])
    ]
    violations = []
    for sense, rhs, terms in constraint_data:
        lhs = sum(coefficient * values[index] for index, coefficient in terms)
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations)
    objective = float(model.ObjVal)
else:
    projected_action = []
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
