import gurobipy as gp
import json
import math

model = gp.Model("SWOR072_patched")
model.Params.OutputFlag = 0

variable_names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
variables = {
    name: model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=name)
    for name in variable_names
}
model.update()

objective_terms = {
    "x_0": 1004,
    "x_1": 962,
    "x_2": 901,
    "x_3": 859,
    "x_4": 798,
    "x_5": 737,
    "x_6": 695,
    "x_7": 634
}
model.setObjective(
    gp.quicksum(coefficient * variables[name] for name, coefficient in objective_terms.items()),
    gp.GRB.MAXIMIZE
)

constraint_specs = [
    ("selected_shift_count", "==", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1, "x_7": 1}),
    ("period_1_minimum_coverage", ">=", 1, {"x_0": 1, "x_3": 1, "x_6": 1}),
    ("period_2_minimum_coverage", ">=", 1, {"x_1": 1, "x_4": 1, "x_7": 1}),
    ("period_3_minimum_coverage", ">=", 1, {"x_2": 1, "x_5": 1}),
    ("minimum_core_shifts", ">=", 2, {"x_0": 1, "x_1": 1, "x_2": 1}),
    ("policy_A_prohibits_B", "<=", 1, {"x_0": 1, "x_1": 1})
]

for constraint_name, constraint_sense, rhs, terms in constraint_specs:
    expression = gp.quicksum(coefficient * variables[name] for name, coefficient in terms.items())
    if constraint_sense == "<=":
        model.addConstr(expression <= rhs, name=constraint_name)
    elif constraint_sense == ">=":
        model.addConstr(expression >= rhs, name=constraint_name)
    else:
        model.addConstr(expression == rhs, name=constraint_name)

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: float(variables[name].X) for name in variable_names}
    projected_action = [int(values[name] >= 0.5) for name in variable_names]
    violations = []
    for constraint_name, constraint_sense, rhs, terms in constraint_specs:
        lhs = sum(coefficient * values[name] for name, coefficient in terms.items())
        if constraint_sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif constraint_sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values.values())
    objective = float(model.ObjVal)
    if not math.isfinite(objective):
        objective = None
else:
    projected_action = [0 for _ in variable_names]
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