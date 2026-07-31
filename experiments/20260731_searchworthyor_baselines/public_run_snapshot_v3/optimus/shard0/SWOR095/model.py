import gurobipy as gp
import json
import math

model = gp.Model("SWOR095_patched")
model.Params.OutputFlag = 0

# REGION variables
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
model.update()

# REGION objective
benefit = [1017, 956, 895, 853, 792, 750, 689]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# REGION segment_1_exactly_one
model.addConstr(x[0] + x[3] + x[6] == 1, name="segment_1_exactly_one")
# REGION segment_2_exactly_one
model.addConstr(x[1] + x[4] == 1, name="segment_2_exactly_one")
# REGION segment_3_exactly_one
model.addConstr(x[2] + x[5] == 1, name="segment_3_exactly_one")
# REGION backup_exclusivity
model.addConstr(x[5] + x[6] <= 1, name="backup_exclusivity")
# REGION eligibility_A_DOC_0E54DEF4E64FB7D2
model.addConstr(x[0] <= 0, name="eligibility_A")

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
    values = [x[i].X for i in range(7)]
    projected_action = [int(round(v)) for v in values]
    checks = [
        (values[0] + values[3] + values[6], "==", 1.0),
        (values[1] + values[4], "==", 1.0),
        (values[2] + values[5], "==", 1.0),
        (values[5] + values[6], "<=", 1.0),
        (values[0], "<=", 0.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(v - round(v)) for v in values)
    objective = model.ObjVal
else:
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
