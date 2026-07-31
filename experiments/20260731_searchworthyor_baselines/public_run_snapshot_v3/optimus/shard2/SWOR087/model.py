import gurobipy as gp
import json
import math

model = gp.Model("SWOR087_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

contribution = [1007, 965, 904, 843, 801, 740, 698]
capacity = [4, 1, 2, 3, 4, 1, 2]

model.setObjective(gp.quicksum(contribution[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) <= 3, name="base_max_enabled")
model.addConstr(gp.quicksum(capacity[i] * x[i] for i in range(7)) <= 7, name="base_capacity")
model.addConstr(x[0] + x[1] <= 1, name="policy_ab_mutual_exclusion")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}

result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": None,
    "projected_action": None,
    "max_constraint_violation": None,
    "integrality_violation": None
}

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected = [int(round(value)) for value in values]
    objective = float(model.ObjVal)

    violations = [
        max(0.0, sum(values) - 3.0),
        max(0.0, sum(capacity[i] * values[i] for i in range(7)) - 7.0),
        max(0.0, values[0] + values[1] - 1.0)
    ]
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))

    integrality_violation = max(abs(value - round(value)) for value in values)
    max_constraint_violation = max(violations)

    result["objective"] = objective if math.isfinite(objective) else None
    result["projected_action"] = projected
    result["max_constraint_violation"] = max_constraint_violation
    result["integrality_violation"] = integrality_violation

print(json.dumps(result, ensure_ascii=False, allow_nan=False))