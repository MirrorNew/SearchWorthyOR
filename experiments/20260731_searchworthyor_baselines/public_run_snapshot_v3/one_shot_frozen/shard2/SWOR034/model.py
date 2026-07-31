import gurobipy as gp
import json

model = gp.Model("SWOR034_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_" + str(i)) for i in range(8)]

utilities = [1000, 958, 897, 855, 794, 752, 691, 630]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) <= 3, name="max_three_modules")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="zone_1_connectivity")
model.addConstr(x[1] + x[4] + x[7] >= 1, name="zone_2_connectivity")
model.addConstr(x[2] + x[5] >= 1, name="zone_3_connectivity")
model.addConstr(x[0] - x[1] - x[4] <= 0, name="module_A_requires_B_or_E")
model.addConstr(x[0] + x[1] <= 1, name="policy_no_A_with_B")

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
    values = [x[i].X for i in range(8)]
    projected_action = [int(round(v)) for v in values]
    checks = [
        (sum(values), "<=", 3.0),
        (values[0] + values[3] + values[6], ">=", 1.0),
        (values[1] + values[4] + values[7], ">=", 1.0),
        (values[2] + values[5], ">=", 1.0),
        (values[0] - values[1] - values[4], "<=", 0.0),
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
    integrality_violation = max(abs(v - round(v)) for v in values)
    objective = model.ObjVal
else:
    objective = None
    projected_action = [0, 0, 0, 0, 0, 0, 0, 0]
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