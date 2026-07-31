import gurobipy as gp
import json
import math

model = gp.Model("SWOR083")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_" + str(i)) for i in range(7)]

profits = [1012, 951, 909, 848, 806, 745, 684]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x[i] for i in range(7)) == 3, name="exactly_three_shifts")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="period_1_coverage")
model.addConstr(x[1] + x[4] >= 1, name="period_2_coverage")
model.addConstr(x[2] + x[5] >= 1, name="period_3_coverage")
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_backup_D")

model.optimize()

status_names = {
    gp.GRB.LOADED: "LOADED",
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.CUTOFF: "CUTOFF",
    gp.GRB.ITERATION_LIMIT: "ITERATION_LIMIT",
    gp.GRB.NODE_LIMIT: "NODE_LIMIT",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.SOLUTION_LIMIT: "SOLUTION_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
    gp.GRB.NUMERIC: "NUMERIC",
    gp.GRB.SUBOPTIMAL: "SUBOPTIMAL",
    gp.GRB.USER_OBJ_LIMIT: "USER_OBJ_LIMIT"
}
status = status_names.get(model.Status, "STATUS_" + str(model.Status))

if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)

    checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[3] + values[6], ">=", 1.0),
        (values[1] + values[4], ">=", 1.0),
        (values[2] + values[5], ">=", 1.0),
        (values[0] + values[3], ">=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    max_constraint_violation = max(violations)
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
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
