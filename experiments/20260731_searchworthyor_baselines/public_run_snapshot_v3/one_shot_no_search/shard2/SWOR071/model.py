import gurobipy as gp
import json
import math

model = gp.Model("SWOR071")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
objective_coefficients = {
    "x_0": 1006,
    "x_1": 964,
    "x_2": 903,
    "x_3": 842,
    "x_4": 800,
    "x_5": 739,
    "x_6": 697
}
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

model.setObjective(
    gp.quicksum(objective_coefficients[name] * x[name] for name in names),
    gp.GRB.MAXIMIZE
)

constraint_specs = [
    ("activate_exactly_3", "==", 3, {name: 1 for name in names}),
    ("emergency_coverage_A_or_B", ">=", 1, {"x_0": 1, "x_1": 1}),
    ("continuity_coverage_B_or_C", ">=", 1, {"x_1": 1, "x_2": 1}),
    ("specialty_coverage_A_or_C", ">=", 1, {"x_0": 1, "x_2": 1}),
    ("core_or_backup_A_or_D", ">=", 1, {"x_0": 1, "x_3": 1})
]

for constraint_name, sense, rhs, terms in constraint_specs:
    lhs = gp.quicksum(coefficient * x[name] for name, coefficient in terms.items())
    if sense == "==":
        model.addConstr(lhs == rhs, name=constraint_name)
    elif sense == ">=":
        model.addConstr(lhs >= rhs, name=constraint_name)
    else:
        model.addConstr(lhs <= rhs, name=constraint_name)

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, "STATUS_" + str(model.Status))

if model.SolCount > 0:
    values = {name: float(x[name].X) for name in names}
    projected_action = [int(round(values[name])) for name in names]
    integrality_violation = max(abs(values[name] - round(values[name])) for name in names)
    violations = []
    for _, sense, rhs, terms in constraint_specs:
        lhs_value = sum(coefficient * values[name] for name, coefficient in terms.items())
        if sense == "==":
            violation = abs(lhs_value - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs_value)
        else:
            violation = max(0.0, lhs_value - rhs)
        violations.append(violation)
    max_constraint_violation = max(violations) if violations else 0.0
    objective = float(model.ObjVal) if math.isfinite(model.ObjVal) else None
else:
    projected_action = [0 for _ in names]
    integrality_violation = None
    max_constraint_violation = None
    objective = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))