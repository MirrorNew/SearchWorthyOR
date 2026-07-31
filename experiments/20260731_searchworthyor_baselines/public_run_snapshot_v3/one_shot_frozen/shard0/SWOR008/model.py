import gurobipy as gp
import json
import math

model = gp.Model("SWOR008_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=name) for name in names}
model.update()

objective_terms = {
    "x_0": 1016.0,
    "x_1": 955.0,
    "x_2": 894.0,
    "x_3": 852.0,
    "x_4": 791.0,
    "x_5": 749.0,
    "x_6": 688.0,
}
model.setObjective(gp.quicksum(coef * x[name] for name, coef in objective_terms.items()), gp.GRB.MAXIMIZE)

constraint_specs = [
    ("select_exactly_3", "==", 3.0, {"x_0": 1.0, "x_1": 1.0, "x_2": 1.0, "x_3": 1.0, "x_4": 1.0, "x_5": 1.0, "x_6": 1.0}),
    ("service_area_1_coverage", ">=", 1.0, {"x_0": 1.0, "x_2": 1.0, "x_4": 1.0, "x_6": 1.0}),
    ("service_area_2_coverage", ">=", 1.0, {"x_1": 1.0, "x_3": 1.0, "x_5": 1.0}),
    ("exactly_one_B_E_G", "==", 1.0, {"x_1": 1.0, "x_4": 1.0, "x_6": 1.0}),
    ("replacement_vehicle_disposition_incompatibility", "<=", 1.0, {"x_0": 1.0, "x_1": 1.0}),
]

for constraint_name, sense, rhs, terms in constraint_specs:
    lhs = gp.quicksum(coef * x[name] for name, coef in terms.items())
    if sense == "<=":
        model.addConstr(lhs <= rhs, name=constraint_name)
    elif sense == ">=":
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
    gp.GRB.INTERRUPTED: "INTERRUPTED",
}
result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": None,
    "projected_action": [],
    "max_constraint_violation": None,
    "integrality_violation": None,
}

if model.SolCount > 0:
    values = {name: float(x[name].X) for name in names}
    projected_action = [int(round(values[name])) for name in names]
    violations = []
    for constraint_name, sense, rhs, terms in constraint_specs:
        lhs_value = math.fsum(coef * values[name] for name, coef in terms.items())
        if sense == "<=":
            violation = max(0.0, lhs_value - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs_value)
        else:
            violation = abs(lhs_value - rhs)
        violations.append(violation)
    result["objective"] = float(model.ObjVal)
    result["projected_action"] = projected_action
    result["max_constraint_violation"] = max(violations, default=0.0)
    result["integrality_violation"] = max(abs(values[name] - round(values[name])) for name in names)

print(json.dumps(result, ensure_ascii=False, allow_nan=False))
