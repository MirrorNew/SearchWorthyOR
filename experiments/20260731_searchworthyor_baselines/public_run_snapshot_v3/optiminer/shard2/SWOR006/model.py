import gurobipy as gp
import json

model = gp.Model("SWOR006_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

variable_specs = [
    ("x_0", 0, 1),
    ("x_1", 0, 1),
    ("x_2", 0, 1),
    ("x_3", 0, 1),
    ("x_4", 0, 1),
    ("x_5", 0, 1),
    ("x_6", 0, 1),
]
x = {
    name: model.addVar(lb=lb, ub=ub, vtype=gp.GRB.BINARY, name=name)
    for name, lb, ub in variable_specs
}
model.update()

objective_terms = {
    "x_0": 1018,
    "x_1": 957,
    "x_2": 896,
    "x_3": 854,
    "x_4": 793,
    "x_5": 751,
}
model.setObjective(
    gp.quicksum(coef * x[name] for name, coef in objective_terms.items()),
    gp.GRB.MAXIMIZE,
)

constraint_specs = [
    ("facility_count", "==", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}),
    ("service_area_1_coverage", ">=", 1, {"x_0": 1, "x_2": 1, "x_4": 1}),
    ("service_area_2_coverage", ">=", 1, {"x_1": 1, "x_3": 1, "x_5": 1}),
    ("core_or_backup", ">=", 1, {"x_0": 1, "x_3": 1}),
    ("credit_claim_requires_build", "<=", 0, {"x_6": 1, "x_0": -1}),
    ("node_A_credit_location_ineligible", "==", 0, {"x_6": 1}),
]

for name, sense, rhs, terms in constraint_specs:
    lhs = gp.quicksum(coef * x[var_name] for var_name, coef in terms.items())
    if sense == "<=":
        model.addConstr(lhs <= rhs, name=name)
    elif sense == ">=":
        model.addConstr(lhs >= rhs, name=name)
    else:
        model.addConstr(lhs == rhs, name=name)

model.optimize()
action_projection = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]

if model.SolCount > 0:
    values = {name: float(var.X) for name, var in x.items()}
    projected_action = [int(round(values[name])) for name in action_projection]
    max_constraint_violation = 0.0
    for _, sense, rhs, terms in constraint_specs:
        lhs = sum(coef * values[var_name] for var_name, coef in terms.items())
        if sense == "<=":
            violation = max(0.0, lhs - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs)
        else:
            violation = abs(lhs - rhs)
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(abs(value - round(value)) for value in values.values())
    result = {
        "status": int(model.Status),
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": float(max_constraint_violation),
        "integrality_violation": float(integrality_violation),
    }
else:
    result = {
        "status": int(model.Status),
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None,
    }

print(json.dumps(result, ensure_ascii=False))