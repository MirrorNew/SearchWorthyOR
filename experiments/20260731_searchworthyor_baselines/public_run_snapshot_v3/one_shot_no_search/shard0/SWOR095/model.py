import gurobipy as gp
import json
import math

model = gp.Model("SWOR095")
model.Params.OutputFlag = 0

# REGION: VARIABLES
names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=name) for name in names]
model.update()

# REGION: OBJECTIVE_TERMS
benefits = [1017.0, 956.0, 895.0, 853.0, 792.0, 750.0, 689.0]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# REGION: SEGMENT_1_EXACTLY_ONE
model.addConstr(x[0] + x[3] + x[6] == 1.0, name="segment_1_exactly_one")

# REGION: SEGMENT_2_EXACTLY_ONE
model.addConstr(x[1] + x[4] == 1.0, name="segment_2_exactly_one")

# REGION: SEGMENT_3_EXACTLY_ONE
model.addConstr(x[2] + x[5] == 1.0, name="segment_3_exactly_one")

# REGION: TERMINAL_RESERVES_INCOMPATIBLE
model.addConstr(x[5] + x[6] <= 1.0, name="terminal_reserves_incompatible")

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
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)

    checks = [
        (values[0] + values[3] + values[6], "==", 1.0),
        (values[1] + values[4], "==", 1.0),
        (values[2] + values[5], "==", 1.0),
        (values[5] + values[6], "<=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0]
    objective = None
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
