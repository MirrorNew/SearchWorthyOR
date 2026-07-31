import gurobipy
import json
import math

model = gurobipy.Model("SWOR013")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}") for i in range(8)]

utility = [1000.0, 958.0, 897.0, 855.0, 794.0, 752.0, 691.0, 630.0]
model.setObjective(gurobipy.quicksum(utility[i] * x[i] for i in range(8)), gurobipy.GRB.MAXIMIZE)

constraint_specs = [
    ("exactly_three_matches", "==", 3.0, {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0, 7: 1.0}),
    ("resource_subject_1_capacity", "<=", 1.0, {0: 1.0, 3: 1.0, 6: 1.0}),
    ("resource_subject_2_capacity", "<=", 1.0, {1: 1.0, 4: 1.0, 7: 1.0}),
    ("resource_subject_3_capacity", "<=", 1.0, {2: 1.0, 5: 1.0}),
    ("core_A_or_D", ">=", 1.0, {0: 1.0, 3: 1.0}),
    ("qualifying_interruption_if_A", "<=", 0.0, {0: 1.0, 6: -1.0, 7: -1.0}),
    ("A_incompatible_with_B", "<=", 1.0, {0: 1.0, 1: 1.0})
]

for name, sense, rhs, terms in constraint_specs:
    lhs = gurobipy.quicksum(coefficient * x[index] for index, coefficient in terms.items())
    if sense == "<=":
        model.addConstr(lhs <= rhs, name=name)
    elif sense == ">=":
        model.addConstr(lhs >= rhs, name=name)
    else:
        model.addConstr(lhs == rhs, name=name)

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
    gurobipy.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(variable.X) for variable in x]
    projected_action = [int(round(value)) for value in values]
    constraint_violations = []
    for name, sense, rhs, terms in constraint_specs:
        lhs_value = sum(coefficient * values[index] for index, coefficient in terms.items())
        if sense == "<=":
            violation = max(0.0, lhs_value - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs_value)
        else:
            violation = abs(lhs_value - rhs)
        constraint_violations.append(violation)
    bound_violations = [max(0.0, -value, value - 1.0) for value in values]
    max_constraint_violation = max(constraint_violations + bound_violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal)
else:
    projected_action = None
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