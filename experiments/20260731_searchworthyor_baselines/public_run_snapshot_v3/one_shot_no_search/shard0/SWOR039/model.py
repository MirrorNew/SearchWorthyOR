import gurobipy as gp
import json
import math

model = gp.Model("SWOR039")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

# VARIABLES
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

# OBJECTIVE
profits = [1005, 963, 902, 841, 799, 738, 696]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# CONSTRAINT_SEGMENT_1
model.addConstr(x[0] + x[3] + x[6] == 1, name="segment_1_exactly_one")

# CONSTRAINT_SEGMENT_2
model.addConstr(x[1] + x[4] == 1, name="segment_2_exactly_one")

# CONSTRAINT_SEGMENT_3
model.addConstr(x[2] + x[5] == 1, name="segment_3_exactly_one")

# CONSTRAINT_CORE_ABC
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_abc_at_least_two")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.Status == gp.GRB.OPTIMAL:
    values = [x[i].X for i in range(7)]
    projected_action = [int(round(value)) for value in values]
    rows = [
        (values[0] + values[3] + values[6], "==", 1.0),
        (values[1] + values[4], "==", 1.0),
        (values[2] + values[5], "==", 1.0),
        (values[0] + values[1] + values[2], ">=", 2.0)
    ]
    violations = []
    for lhs, sense, rhs in rows:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
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
print(json.dumps(result, ensure_ascii=False))
