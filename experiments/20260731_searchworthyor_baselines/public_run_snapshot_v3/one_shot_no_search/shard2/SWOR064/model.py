import gurobipy as gp
import json
import math

model = gp.Model("SWOR064")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}
model.update()

objective_terms = {
    "x_0": 1001,
    "x_1": 959,
    "x_2": 898,
    "x_3": 856,
    "x_4": 795,
    "x_5": 753,
    "x_6": 692,
    "x_7": 631
}
model.setObjective(gp.quicksum(coef * x[name] for name, coef in objective_terms.items()), gp.GRB.MAXIMIZE)

constraint_specs = [
    ("facility_count", "==", 3, {name: 1 for name in names}),
    ("service_area_1_coverage", ">=", 1, {"x_0": 1, "x_2": 1, "x_4": 1, "x_6": 1}),
    ("service_area_2_coverage", ">=", 1, {"x_1": 1, "x_3": 1, "x_5": 1, "x_7": 1}),
    ("core_candidates_minimum", ">=", 2, {"x_0": 1, "x_1": 1, "x_2": 1})
]

for constraint_name, sense, rhs, terms in constraint_specs:
    lhs = gp.quicksum(coef * x[name] for name, coef in terms.items())
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
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: float(x[name].X) for name in names}
    projected_action = [int(round(values[name])) for name in names]
    objective = float(model.ObjVal)
    violations = []
    for constraint_name, sense, rhs, terms in constraint_specs:
        lhs_value = sum(coef * values[name] for name, coef in terms.items())
        if sense == "==":
            violation = abs(lhs_value - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs_value)
        else:
            violation = max(0.0, lhs_value - rhs)
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
print(json.dumps(result, ensure_ascii=False))
