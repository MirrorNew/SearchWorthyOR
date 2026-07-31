import gurobipy as gp
import json
import math

model = gp.Model("SWOR055_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

objective_terms = {
    "x_0": 1013,
    "x_1": 952,
    "x_2": 910,
    "x_3": 849,
    "x_4": 788,
    "x_5": 746,
    "x_6": 685
}
model.setObjective(gp.quicksum(coef * x[name] for name, coef in objective_terms.items()), gp.GRB.MAXIMIZE)

constraint_specs = [
    ("enable_exactly_three_units", "==", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1}),
    ("emergency_coverage_A_or_B", ">=", 1, {"x_0": 1, "x_1": 1}),
    ("continuity_coverage_B_or_C", ">=", 1, {"x_1": 1, "x_2": 1}),
    ("specialty_coverage_A_or_C", ">=", 1, {"x_0": 1, "x_2": 1}),
    ("exactly_one_of_B_E_G", "==", 1, {"x_1": 1, "x_4": 1, "x_6": 1}),
    ("federal_existing_source_mercury_control", ">=", 1, {"x_5": 1, "x_6": 1})
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
    gp.GRB.UNBOUNDED: "UNBOUNDED"
}
status = status_names.get(model.Status, "STATUS_" + str(model.Status))

if model.SolCount > 0:
    values = {name: float(x[name].X) for name in names}
    projected_action = [int(round(values[name])) for name in names]
    integrality_violation = max(abs(values[name] - round(values[name])) for name in names)
    violations = []
    for _, sense, rhs, terms in constraint_specs:
        lhs_value = sum(coef * values[name] for name, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs_value - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs_value))
        else:
            violations.append(abs(lhs_value - rhs))
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": float(max(violations) if violations else 0.0),
        "integrality_violation": float(integrality_violation)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": None,
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))