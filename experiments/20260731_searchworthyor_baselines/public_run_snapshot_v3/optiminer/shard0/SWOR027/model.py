import gurobipy as gp
import json
import math

model = gp.Model("SWOR027_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
benefits = [1008, 947, 905, 844, 802, 741, 699, 638]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]

model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

rows = [
    ("select_exactly_three", {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1}, "==", 3),
    ("front_segment_requirement", {0: 1, 1: 1, 3: 1, 6: 1}, ">=", 1),
    ("back_segment_frozen_requirement", {1: 1, 2: 1, 4: 1, 7: 1}, ">=", 1),
    ("core_or_backup_requirement", {0: 1, 3: 1}, ">=", 1),
    ("evidence_A_ineligible", {0: 1}, "==", 0)
]

for row_name, coefficients, row_sense, rhs in rows:
    expression = gp.quicksum(coefficient * x[index] for index, coefficient in coefficients.items())
    if row_sense == "==":
        model.addConstr(expression == rhs, name=row_name)
    elif row_sense == ">=":
        model.addConstr(expression >= rhs, name=row_name)
    else:
        model.addConstr(expression <= rhs, name=row_name)

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
    values = [variable.X for variable in x]
    projected_action = [int(round(value)) for value in values]
    max_constraint_violation = 0.0
    for row_name, coefficients, row_sense, rhs in rows:
        lhs = sum(coefficient * values[index] for index, coefficient in coefficients.items())
        if row_sense == "==":
            violation = abs(lhs - rhs)
        elif row_sense == ">=":
            violation = max(0.0, rhs - lhs)
        else:
            violation = max(0.0, lhs - rhs)
        max_constraint_violation = max(max_constraint_violation, violation)
    for value in values:
        max_constraint_violation = max(max_constraint_violation, max(0.0, -value), max(0.0, value - 1.0))
    integrality_violation = max(abs(value - round(value)) for value in values)
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
print(json.dumps(result, ensure_ascii=False, allow_nan=False))