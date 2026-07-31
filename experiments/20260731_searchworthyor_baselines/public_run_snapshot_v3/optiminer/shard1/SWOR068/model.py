import gurobipy as gp
import json
import math

model = gp.Model("SWOR068_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

objective_terms = {
    "x_0": 1008,
    "x_1": 947,
    "x_2": 905,
    "x_3": 844,
    "x_4": 802,
    "x_5": 741,
}
model.setObjective(gp.quicksum(coef * x[name] for name, coef in objective_terms.items()), gp.GRB.MAXIMIZE)

constraint_specs = [
    ("select_exactly_3", "==", 3.0, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}),
    ("emergency_coverage_A_or_B", ">=", 1.0, {"x_0": 1, "x_1": 1}),
    ("continuity_coverage_B_or_C", ">=", 1.0, {"x_1": 1, "x_2": 1}),
    ("specialty_coverage_A_or_C", ">=", 1.0, {"x_0": 1, "x_2": 1}),
    ("at_least_two_core_candidates", ">=", 2.0, {"x_0": 1, "x_1": 1, "x_2": 1}),
    ("policy_A_excludes_B", "<=", 1.0, {"x_0": 1, "x_1": 1}),
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
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: float(x[name].X) for name in names}
    projected_action = [int(values[name] >= 0.5) for name in names]
    objective = float(model.ObjVal)
    violations = []
    for cname, sense, rhs, terms in constraint_specs:
        lhs = sum(coef * values[name] for name, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(values[name] - round(values[name])) for name in names)
else:
    objective = None
    projected_action = [0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False))