import gurobipy as gp
import json
import math

m = gp.Model("SWOR044_patched")
m.Params.OutputFlag = 0

order = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
x = {name: m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in order}

objective_terms = {
    "x_0": 1008,
    "x_1": 947,
    "x_2": 905,
    "x_3": 844,
    "x_4": 802,
    "x_5": 741,
    "x_6": 699
}
m.setObjective(gp.quicksum(coef * x[name] for name, coef in objective_terms.items()), gp.GRB.MAXIMIZE)

rows = [
    ("exactly_three_assignments", "==", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1}),
    ("resource_subject_1_at_most_one", "<=", 1, {"x_0": 1, "x_3": 1, "x_6": 1}),
    ("resource_subject_2_at_most_one", "<=", 1, {"x_1": 1, "x_4": 1}),
    ("resource_subject_3_at_most_one", "<=", 1, {"x_2": 1, "x_5": 1}),
    ("B_E_G_exactly_one", "==", 1, {"x_1": 1, "x_4": 1, "x_6": 1}),
    ("policy_A_B_mutex", "<=", 1, {"x_0": 1, "x_1": 1})
]

for row_name, sense, rhs, terms in rows:
    lhs = gp.quicksum(coef * x[name] for name, coef in terms.items())
    if sense == "<=":
        m.addConstr(lhs <= rhs, name=row_name)
    elif sense == ">=":
        m.addConstr(lhs >= rhs, name=row_name)
    else:
        m.addConstr(lhs == rhs, name=row_name)

m.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(m.Status, str(m.Status))

if m.SolCount > 0:
    values = {name: float(x[name].X) for name in order}
    projected_action = [int(values[name] >= 0.5) for name in order]
    violations = []
    for row_name, sense, rhs, terms in rows:
        lhs_value = sum(coef * values[name] for name, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs_value - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs_value))
        else:
            violations.append(abs(lhs_value - rhs))
    for name in order:
        violations.append(max(0.0, -values[name], values[name] - 1.0))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(values[name] - round(values[name])) for name in order)
    result = {
        "status": status,
        "objective": float(m.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": float(max_constraint_violation),
        "integrality_violation": float(integrality_violation)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0 for _ in order],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))
