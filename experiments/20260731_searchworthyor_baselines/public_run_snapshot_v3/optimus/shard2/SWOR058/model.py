import gurobipy as gp
import json

model = gp.Model("SWOR058_patched")
model.Params.OutputFlag = 0

projection = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
x = {
    name: model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=name)
    for name in projection
}

objective_terms = {
    "x_0": 1001.0,
    "x_1": 959.0,
    "x_2": 898.0,
    "x_3": 856.0,
    "x_4": 795.0,
    "x_5": 753.0
}
model.setObjective(
    gp.quicksum(coef * x[name] for name, coef in objective_terms.items()),
    gp.GRB.MAXIMIZE
)

model.addConstr(x["x_0"] + x["x_3"] == 1.0, name="segment_1_exactly_one")
model.addConstr(x["x_1"] + x["x_4"] == 1.0, name="segment_2_exactly_one")
model.addConstr(x["x_2"] + x["x_5"] == 1.0, name="segment_3_exactly_one")
model.addConstr(x["x_1"] + x["x_4"] + x["x_5"] == 1.0, name="core_B_E_F_exactly_one")
model.addConstr(x["x_0"] + x["x_1"] <= 1.0, name="rest_10h_A_B_conflict")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.SUBOPTIMAL: "SUBOPTIMAL"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: float(x[name].X) for name in projection}
    projected_action = [int(round(values[name])) for name in projection]

    rows = [
        ({"x_0": 1.0, "x_3": 1.0}, "==", 1.0),
        ({"x_1": 1.0, "x_4": 1.0}, "==", 1.0),
        ({"x_2": 1.0, "x_5": 1.0}, "==", 1.0),
        ({"x_1": 1.0, "x_4": 1.0, "x_5": 1.0}, "==", 1.0),
        ({"x_0": 1.0, "x_1": 1.0}, "<=", 1.0)
    ]
    violations = [max(0.0, -value, value - 1.0) for value in values.values()]
    for terms, sense, rhs in rows:
        lhs = sum(coef * values[name] for name, coef in terms.items())
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))

    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": float(max(violations)),
        "integrality_violation": float(max(abs(value - round(value)) for value in values.values()))
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": None,
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, sort_keys=True))
