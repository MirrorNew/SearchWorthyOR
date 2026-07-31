import gurobipy
import json
import math

model = gurobipy.Model("SWOR099")
model.Params.OutputFlag = 0

# variables
x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
model.update()

# objective
objective_coefficients = [1015, 954, 912, 851, 790, 748, 687, 645]
model.setObjective(
    gurobipy.quicksum(objective_coefficients[i] * x[i] for i in range(8)),
    gurobipy.GRB.MAXIMIZE,
)

# base constraints and policy patch constraint
constraint_specs = [
    ("choose_exactly_3", "==", 3.0, {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0, 7: 1.0}),
    ("front_arrival_at_least_one", ">=", 1.0, {0: 1.0, 1: 1.0, 3: 1.0, 6: 1.0}),
    ("back_arrival_at_least_one", ">=", 1.0, {1: 1.0, 2: 1.0, 4: 1.0, 7: 1.0}),
    ("exactly_one_B_E_H", "==", 1.0, {1: 1.0, 4: 1.0, 7: 1.0}),
    ("nslp_fruit_or_vegetable_required", ">=", 1.0, {6: 1.0, 7: 1.0}),
]

for name, sense, rhs, terms in constraint_specs:
    lhs = gurobipy.quicksum(coefficient * x[index] for index, coefficient in terms.items())
    if sense == "<=":
        model.addConstr(lhs <= rhs, name=name)
    elif sense == ">=":
        model.addConstr(lhs >= rhs, name=name)
    else:
        model.addConstr(lhs == rhs, name=name)

# solve and report
model.optimize()
status_labels = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_labels.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(variable.X) for variable in x]
    projected_action = [int(round(value)) for value in values]
    violations = []
    for name, sense, rhs, terms in constraint_specs:
        lhs_value = sum(coefficient * values[index] for index, coefficient in terms.items())
        if sense == "<=":
            violation = max(0.0, lhs_value - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs_value)
        else:
            violation = abs(lhs_value - rhs)
        violations.append(violation)
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal)
else:
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None
    objective = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}, ensure_ascii=False))