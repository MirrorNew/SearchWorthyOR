import gurobipy as gp
import json
import math

model = gp.Model("SWOR078")
model.Params.OutputFlag = 0

# code_region: variables
names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]
model.update()

# code_region: objective
utilities = [1017, 956, 895, 853, 792, 750]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

# code_region: constraint:max_enabled_modules
model.addConstr(gp.quicksum(x) <= 3, name="max_enabled_modules")

# code_region: constraint:communication_zone_1
model.addConstr(x[0] + x[3] >= 1, name="communication_zone_1")

# code_region: constraint:communication_zone_2
model.addConstr(x[1] + x[4] >= 1, name="communication_zone_2")

# code_region: constraint:communication_zone_3
model.addConstr(x[2] + x[5] >= 1, name="communication_zone_3")

# code_region: constraint:module_A_requires_B_or_E
model.addConstr(-x[0] + x[1] + x[4] >= 0, name="module_A_requires_B_or_E")

# code_region: constraint:modules_E_F_mutually_exclusive
model.addConstr(x[4] + x[5] <= 1, name="modules_E_F_mutually_exclusive")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [v.X for v in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)
    lhs_values = [
        sum(values),
        values[0] + values[3],
        values[1] + values[4],
        values[2] + values[5],
        -values[0] + values[1] + values[4],
        values[4] + values[5]
    ]
    specifications = [
        ("<=", 3),
        (">=", 1),
        (">=", 1),
        (">=", 1),
        (">=", 0),
        ("<=", 1)
    ]
    violations = []
    for lhs, specification in zip(lhs_values, specifications):
        sense, rhs = specification
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values)
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
