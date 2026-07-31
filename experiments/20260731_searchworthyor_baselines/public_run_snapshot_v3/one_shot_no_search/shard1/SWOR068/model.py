import gurobipy as gp
import json
import math

model = gp.Model("SWOR068")
model.Params.OutputFlag = 0

variable_names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
variables = {
    name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name)
    for name in variable_names
}
model.update()

objective_terms = {
    "x_0": 1008,
    "x_1": 947,
    "x_2": 905,
    "x_3": 844,
    "x_4": 802,
    "x_5": 741
}
model.setObjective(
    gp.quicksum(coefficient * variables[name] for name, coefficient in objective_terms.items()),
    gp.GRB.MAXIMIZE
)

constraints_data = [
    ("select_exactly_3", "==", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}),
    ("emergency_A_or_B", ">=", 1, {"x_0": 1, "x_1": 1}),
    ("continuity_B_or_C", ">=", 1, {"x_1": 1, "x_2": 1}),
    ("specialty_A_or_C", ">=", 1, {"x_0": 1, "x_2": 1}),
    ("core_ABC_at_least_2", ">=", 2, {"x_0": 1, "x_1": 1, "x_2": 1})
]

for constraint_name, constraint_sense, rhs, terms in constraints_data:
    expression = gp.quicksum(coefficient * variables[name] for name, coefficient in terms.items())
    if constraint_sense == "==":
        model.addConstr(expression == rhs, name=constraint_name)
    elif constraint_sense == ">=":
        model.addConstr(expression >= rhs, name=constraint_name)
    else:
        model.addConstr(expression <= rhs, name=constraint_name)

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
    values = {name: variables[name].X for name in variable_names}
    projected_action = [int(values[name] >= 0.5) for name in variable_names]
    integrality_violation = max(abs(value - round(value)) for value in values.values())
    violations = []
    for _, constraint_sense, rhs, terms in constraints_data:
        lhs = sum(coefficient * values[name] for name, coefficient in terms.items())
        if constraint_sense == "==":
            violations.append(abs(lhs - rhs))
        elif constraint_sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    objective = model.ObjVal if math.isfinite(model.ObjVal) else None
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