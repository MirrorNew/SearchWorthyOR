import gurobipy as gp
import json
import math

model = gp.Model("SWOR055_patched")
model.Params.OutputFlag = 0

names = [f"x_{i}" for i in range(7)]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=name) for name in names}

utilities = [1013, 952, 910, 849, 788, 746, 685]
model.setObjective(gp.quicksum(utilities[i] * x[names[i]] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x[name] for name in names) == 3, name="select_exactly_3")
model.addConstr(x["x_0"] + x["x_1"] >= 1, name="emergency_A_or_B")
model.addConstr(x["x_1"] + x["x_2"] >= 1, name="continuity_B_or_C")
model.addConstr(x["x_0"] + x["x_2"] >= 1, name="specialty_A_or_C")
model.addConstr(x["x_1"] + x["x_4"] + x["x_6"] == 1, name="exactly_one_B_E_G")
model.addConstr(x["x_5"] + x["x_6"] >= 1, name="policy_mercury_control_F_or_G")

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
    projected_action = [int(round(x[name].X)) for name in names]
    objective = float(model.ObjVal)
    rows = [
        ("==", 3.0, {name: 1.0 for name in names}),
        (">=", 1.0, {"x_0": 1.0, "x_1": 1.0}),
        (">=", 1.0, {"x_1": 1.0, "x_2": 1.0}),
        (">=", 1.0, {"x_0": 1.0, "x_2": 1.0}),
        ("==", 1.0, {"x_1": 1.0, "x_4": 1.0, "x_6": 1.0}),
        (">=", 1.0, {"x_5": 1.0, "x_6": 1.0})
    ]
    violations = []
    for sense, rhs, terms in rows:
        lhs = sum(coef * x[name].X for name, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = float(max(violations, default=0.0))
    integrality_violation = float(max(abs(x[name].X - round(x[name].X)) for name in names))
else:
    projected_action = None
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
print(json.dumps(result, ensure_ascii=False, allow_nan=False))