import gurobipy as gp
import json
import math

model = gp.Model("SWOR077_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}
model.update()

objective_coefficients = {
    "x_0": 1004, "x_1": 962, "x_2": 901, "x_3": 859,
    "x_4": 798, "x_5": 737, "x_6": 695, "x_7": 634
}
model.setObjective(
    gp.quicksum(objective_coefficients[name] * x[name] for name in names),
    gp.GRB.MAXIMIZE
)

constraint_data = [
    ("select_exactly_3", "==", 3, {name: 1 for name in names}),
    ("emergency_coverage", ">=", 1, {"x_0": 1, "x_1": 1}),
    ("continuity_of_care", ">=", 1, {"x_1": 1, "x_2": 1}),
    ("specialty_coverage", ">=", 1, {"x_0": 1, "x_2": 1}),
    ("core_backup_emergency_exactly_one", "==", 1, {"x_1": 1, "x_4": 1, "x_7": 1}),
    ("policy_A_ineligible", "==", 0, {"x_0": 1})
]

for constraint_name, constraint_sense, rhs, terms in constraint_data:
    lhs = gp.quicksum(coefficient * x[name] for name, coefficient in terms.items())
    if constraint_sense == "<=":
        model.addConstr(lhs <= rhs, name=constraint_name)
    elif constraint_sense == ">=":
        model.addConstr(lhs >= rhs, name=constraint_name)
    else:
        model.addConstr(lhs == rhs, name=constraint_name)

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

if model.SolCount > 0:
    values = {name: float(x[name].X) for name in names}
    projected_action = [1 if values[name] >= 0.5 else 0 for name in names]
    violations = []
    for constraint_name, constraint_sense, rhs, terms in constraint_data:
        lhs_value = sum(coefficient * values[name] for name, coefficient in terms.items())
        if constraint_sense == "<=":
            violations.append(max(0.0, lhs_value - rhs))
        elif constraint_sense == ">=":
            violations.append(max(0.0, rhs - lhs_value))
        else:
            violations.append(abs(lhs_value - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(min(abs(value), abs(1.0 - value)) for value in values.values())
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
    "integrality_violation": integrality_violation
}, ensure_ascii=False))