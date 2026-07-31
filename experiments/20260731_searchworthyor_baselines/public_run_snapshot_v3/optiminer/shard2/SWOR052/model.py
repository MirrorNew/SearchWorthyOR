import gurobipy as gp
import json

model = gp.Model("SWOR052_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

# MODEL_SLOT variables/action_projection: A, B, C, D, E, F, G, H
names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]

# MODEL_SLOT objective
benefits = [1006, 964, 903, 842, 800, 739, 697, 636]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

# MODEL_SLOT constraints/exactly_three_assignments
model.addConstr(gp.quicksum(x) == 3, name="exactly_three_assignments")
# MODEL_SLOT constraints/mutex_subject_1
model.addConstr(x[0] + x[3] + x[6] <= 1, name="mutex_subject_1")
# MODEL_SLOT constraints/mutex_subject_2
model.addConstr(x[1] + x[4] + x[7] <= 1, name="mutex_subject_2")
# MODEL_SLOT constraints/mutex_subject_3
model.addConstr(x[2] + x[5] <= 1, name="mutex_subject_3")
# MODEL_SLOT constraints/policy保障至少一项; evidence DOC-032E0A410A8D3DBB
model.addConstr(x[6] + x[7] >= 1, name="policy保障至少一项")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": None,
    "projected_action": [],
    "max_constraint_violation": None,
    "integrality_violation": None
}

if model.SolCount > 0:
    values = [var.X for var in x]
    result["objective"] = float(model.ObjVal)
    result["projected_action"] = [int(round(value)) for value in values]

    checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[3] + values[6], "<=", 1.0),
        (values[1] + values[4] + values[7], "<=", 1.0),
        (values[2] + values[5], "<=", 1.0),
        (values[6] + values[7], ">=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    result["max_constraint_violation"] = float(max(violations))
    result["integrality_violation"] = float(max(abs(value - round(value)) for value in values))

print(json.dumps(result, ensure_ascii=False))
