import gurobipy as gp
import json
import math

model = gp.Model("SWOR077")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
values = [1004, 962, 901, 859, 798, 737, 695, 634]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

model.setObjective(gp.quicksum(values[i] * x[names[i]] for i in range(8)), gp.GRB.MAXIMIZE)

constraint_data = [
    ("exactly_three_units", "==", 3.0, {name: 1.0 for name in names}),
    ("emergency_coverage", ">=", 1.0, {"x_0": 1.0, "x_1": 1.0}),
    ("continuity_coverage", ">=", 1.0, {"x_1": 1.0, "x_2": 1.0}),
    ("specialty_coverage", ">=", 1.0, {"x_0": 1.0, "x_2": 1.0}),
    ("core_backup_terminal_exactly_one", "==", 1.0, {"x_1": 1.0, "x_4": 1.0, "x_7": 1.0})
]

for cname, sense, rhs, terms in constraint_data:
    expr = gp.quicksum(coef * x[var_name] for var_name, coef in terms.items())
    if sense == "<=":
        model.addConstr(expr <= rhs, name=cname)
    elif sense == ">=":
        model.addConstr(expr >= rhs, name=cname)
    else:
        model.addConstr(expr == rhs, name=cname)

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
    raw = [float(x[name].X) for name in names]
    projected_action = [int(round(v)) for v in raw]
    integrality_violation = max(abs(v - round(v)) for v in raw)
    violations = []
    for cname, sense, rhs, terms in constraint_data:
        lhs = sum(coef * raw[names.index(var_name)] for var_name, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    for v in raw:
        violations.append(max(0.0, -v, v - 1.0))
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0 for _ in names],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))
