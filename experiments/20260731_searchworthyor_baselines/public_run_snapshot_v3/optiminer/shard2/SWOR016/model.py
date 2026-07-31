import gurobipy as gp
import json
import math

model = gp.Model("SWOR016_patched")
model.Params.OutputFlag = 0

projection = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=name) for name in projection}

objective_terms = {
    "x_0": 1007.0,
    "x_1": 965.0,
    "x_2": 904.0,
    "x_3": 843.0,
    "x_4": 801.0,
    "x_5": 740.0,
    "x_6": 698.0,
    "x_7": 637.0
}
model.setObjective(gp.quicksum(coef * x[name] for name, coef in objective_terms.items()), gp.GRB.MAXIMIZE)

constraint_specs = [
    ("c_build_exactly_3", "==", 3.0, {"x_0": 1.0, "x_1": 1.0, "x_2": 1.0, "x_3": 1.0, "x_4": 1.0, "x_5": 1.0, "x_6": 1.0, "x_7": 1.0}),
    ("c_service_area_1", ">=", 1.0, {"x_0": 1.0, "x_2": 1.0, "x_4": 1.0, "x_6": 1.0}),
    ("c_service_area_2", ">=", 1.0, {"x_1": 1.0, "x_3": 1.0, "x_5": 1.0, "x_7": 1.0}),
    ("c_exactly_one_B_E_H", "==", 1.0, {"x_1": 1.0, "x_4": 1.0, "x_7": 1.0}),
    ("c_policy_A_excludes_B", "<=", 1.0, {"x_0": 1.0, "x_1": 1.0})
]

for cname, sense, rhs, terms in constraint_specs:
    lhs = gp.quicksum(coef * x[name] for name, coef in terms.items())
    if sense == "<=":
        model.addConstr(lhs <= rhs, name=cname)
    elif sense == ">=":
        model.addConstr(lhs >= rhs, name=cname)
    else:
        model.addConstr(lhs == rhs, name=cname)

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
    values = {name: float(x[name].X) for name in projection}
    projected_action = [int(round(values[name])) for name in projection]
    integrality_violation = max(abs(values[name] - round(values[name])) for name in projection)
    max_constraint_violation = 0.0
    for cname, sense, rhs, terms in constraint_specs:
        lhs_value = sum(coef * values[name] for name, coef in terms.items())
        if sense == "<=":
            violation = max(0.0, lhs_value - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs_value)
        else:
            violation = abs(lhs_value - rhs)
        max_constraint_violation = max(max_constraint_violation, violation)
    objective = float(model.ObjVal) if math.isfinite(model.ObjVal) else None
else:
    projected_action = [0 for _ in projection]
    integrality_violation = None
    max_constraint_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
