import gurobipy as gp
import json
import math

model = gp.Model("SWOR053_patched")
model.Params.OutputFlag = 0

variable_names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
x = {
    name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name)
    for name in variable_names
}

objective_terms = {
    "x_0": 1006,
    "x_1": 964,
    "x_2": 903,
    "x_3": 842,
    "x_4": 800,
    "x_5": 739,
    "x_6": 697,
    "x_7": 636
}
model.setObjective(
    gp.quicksum(coefficient * x[name] for name, coefficient in objective_terms.items()),
    gp.GRB.MAXIMIZE
)

constraint_specs = [
    ("module_limit", "<=", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1, "x_7": 1}),
    ("zone_1_connectivity", ">=", 1, {"x_0": 1, "x_3": 1, "x_6": 1}),
    ("zone_2_connectivity", ">=", 1, {"x_1": 1, "x_4": 1, "x_7": 1}),
    ("zone_3_connectivity", ">=", 1, {"x_2": 1, "x_5": 1}),
    ("module_A_requires_B_or_E", "<=", 0, {"x_0": 1, "x_1": -1, "x_4": -1}),
    ("core_candidate_minimum", ">=", 2, {"x_0": 1, "x_1": 1, "x_2": 1}),
    ("policy_safeguard_option", ">=", 1, {"x_6": 1, "x_7": 1})
]

for constraint_name, constraint_sense, rhs, terms in constraint_specs:
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
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
    gp.GRB.SUBOPTIMAL: "SUBOPTIMAL"
}
status = status_names.get(model.Status, "STATUS_" + str(model.Status))

if model.SolCount > 0:
    values = {name: float(x[name].X) for name in variable_names}
    projected_action = [int(round(values[name])) for name in variable_names]
    objective = float(model.ObjVal)
    violations = []
    for _, constraint_sense, rhs, terms in constraint_specs:
        lhs_value = sum(coefficient * values[name] for name, coefficient in terms.items())
        if constraint_sense == "<=":
            violations.append(max(0.0, lhs_value - rhs))
        elif constraint_sense == ">=":
            violations.append(max(0.0, rhs - lhs_value))
        else:
            violations.append(abs(lhs_value - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(values[name] - round(values[name])) for name in variable_names)
else:
    objective = None
    projected_action = [0 for _ in variable_names]
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
