import gurobipy as gp
import json
import math

model = gp.Model("SWOR098")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

objective_coefficients = {
    "x_0": 1009, "x_1": 948, "x_2": 906, "x_3": 845,
    "x_4": 803, "x_5": 742, "x_6": 700, "x_7": 639
}
model.setObjective(
    gp.quicksum(objective_coefficients[name] * x[name] for name in names),
    gp.GRB.MAXIMIZE
)

rows = [
    ("max_enabled_units", "<=", 3, {name: 1 for name in names}),
    ("grid_resource_capacity", "<=", 8, {"x_0": 3, "x_1": 4, "x_2": 1, "x_3": 2, "x_4": 3, "x_5": 4, "x_6": 1, "x_7": 2}),
    ("minimum_clean_capability", ">=", 1, {"x_0": 1, "x_3": 1, "x_6": 1}),
    ("minimum_backup_capability", ">=", 1, {"x_1": 1, "x_4": 1, "x_7": 1}),
    ("minimum_core_candidates", ">=", 2, {"x_0": 1, "x_1": 1, "x_2": 1})
]

for row_name, row_sense, rhs, terms in rows:
    lhs = gp.quicksum(coefficient * x[name] for name, coefficient in terms.items())
    if row_sense == "<=":
        model.addConstr(lhs <= rhs, name=row_name)
    elif row_sense == ">=":
        model.addConstr(lhs >= rhs, name=row_name)
    else:
        model.addConstr(lhs == rhs, name=row_name)

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: x[name].X for name in names}
    projected_action = [int(round(values[name])) for name in names]
    objective = float(model.ObjVal)
    violations = []
    for row_name, row_sense, rhs, terms in rows:
        lhs_value = sum(coefficient * values[name] for name, coefficient in terms.items())
        if row_sense == "<=":
            violation = max(0.0, lhs_value - rhs)
        elif row_sense == ">=":
            violation = max(0.0, rhs - lhs_value)
        else:
            violation = abs(lhs_value - rhs)
        violations.append(violation)
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(values[name] - round(values[name])) for name in names)
else:
    projected_action = []
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
