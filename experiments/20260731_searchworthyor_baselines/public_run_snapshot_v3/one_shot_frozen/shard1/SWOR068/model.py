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
    ("select_exactly_three", "==", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}),
    ("emergency_coverage_ab", ">=", 1, {"x_0": 1, "x_1": 1}),
    ("continuity_coverage_bc", ">=", 1, {"x_1": 1, "x_2": 1}),
    ("specialty_coverage_ac", ">=", 1, {"x_0": 1, "x_2": 1}),
    ("core_candidates_at_least_two", ">=", 2, {"x_0": 1, "x_1": 1, "x_2": 1}),
    ("compliance_a_excludes_b", "<=", 1, {"x_0": 1, "x_1": 1}),
]

for cname, sense, rhs, terms in constraint_specs:
    lhs = gp.quicksum(coef * x[name] for name, coef in terms.items())
    if sense == "==":
        model.addConstr(lhs == rhs, name=cname)
    elif sense == ">=":
        model.addConstr(lhs >= rhs, name=cname)
    else:
        model.addConstr(lhs <= rhs, name=cname)

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: float(x[name].X) for name in names}
    projected_action = [int(round(values[name])) for name in names]
    objective = float(model.ObjVal)
    violations = []
    for cname, sense, rhs, terms in constraint_specs:
        lhs_value = sum(coef * values[name] for name, coef in terms.items())
        if sense == "==":
            violation = abs(lhs_value - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs_value)
        else:
            violation = max(0.0, lhs_value - rhs)
        violations.append(violation)
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(min(abs(values[name]), abs(values[name] - 1.0)) for name in names)
else:
    projected_action = [0 for _ in names]
    objective = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))