import gurobipy as gp
import json
import math

model = gp.Model("SWOR037")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}") for i in range(8)]

objective_coefficients = [1013, 952, 910, 849, 788, 746, 685, 643]
model.setObjective(
    gp.quicksum(objective_coefficients[i] * x[i] for i in range(8)),
    gp.GRB.MAXIMIZE,
)

constraint_data = [
    ("maximum_three_modules", "<=", 3.0, {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0, 7: 1.0}),
    ("zone_1_connectivity", ">=", 1.0, {0: 1.0, 3: 1.0, 6: 1.0}),
    ("zone_2_connectivity", ">=", 1.0, {1: 1.0, 4: 1.0, 7: 1.0}),
    ("zone_3_connectivity", ">=", 1.0, {2: 1.0, 5: 1.0}),
    ("module_A_requires_B_or_E", ">=", 0.0, {0: -1.0, 1: 1.0, 4: 1.0}),
    ("module_A_or_D_required", ">=", 1.0, {0: 1.0, 3: 1.0}),
]

for name, sense, rhs, terms in constraint_data:
    expression = gp.quicksum(coefficient * x[index] for index, coefficient in terms.items())
    if sense == "<=":
        model.addConstr(expression <= rhs, name=name)
    elif sense == ">=":
        model.addConstr(expression >= rhs, name=name)
    else:
        model.addConstr(expression == rhs, name=name)

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(variable.X) for variable in x]
    projected_action = [int(round(value)) for value in values]
    violations = []
    for name, sense, rhs, terms in constraint_data:
        lhs = sum(coefficient * values[index] for index, coefficient in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal)
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
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))