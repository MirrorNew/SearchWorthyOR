import gurobipy as gp
import json
import math

model = gp.Model("SWOR027")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_" + str(i)) for i in range(8)]

profits = [1008, 947, 905, 844, 802, 741, 699, 638]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x[i] for i in range(8)) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="front_supply_at_least_1")
model.addConstr(x[1] + x[2] + x[4] + x[7] >= 1, name="back_supply_at_least_1")
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_D_at_least_1")

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

result = {
    "status": status,
    "objective": None,
    "projected_action": [],
    "max_constraint_violation": None,
    "integrality_violation": None
}

if model.SolCount > 0:
    values = [x[i].X for i in range(8)]
    projected = [1 if value >= 0.5 else 0 for value in values]

    lhs_values = [
        sum(values),
        values[0] + values[1] + values[3] + values[6],
        values[1] + values[2] + values[4] + values[7],
        values[0] + values[3]
    ]
    senses = ["==", ">=", ">=", ">="]
    rhs_values = [3.0, 1.0, 1.0, 1.0]
    violations = []
    for lhs, sense, rhs in zip(lhs_values, senses, rhs_values):
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))

    result["objective"] = model.ObjVal
    result["projected_action"] = projected
    result["max_constraint_violation"] = max(violations)
    result["integrality_violation"] = max(abs(value - round(value)) for value in values)

print(json.dumps(result, ensure_ascii=False, allow_nan=False))
