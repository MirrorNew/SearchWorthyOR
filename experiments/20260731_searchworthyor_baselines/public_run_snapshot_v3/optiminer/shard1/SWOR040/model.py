import gurobipy as gp
import json
import math

model = gp.Model("SWOR040_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]
model.update()

# objective: maximize total network coverage benefit
benefits = [1011, 950, 908, 847, 805, 744]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

# frozen base constraints
model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[2] + x[4] >= 1, name="cover_service_area_1")
model.addConstr(x[1] + x[3] + x[5] >= 1, name="cover_service_area_2")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_at_least_2")

# policy patch from DOC-AA6DDC507762D3C3
model.addConstr(x[0] + x[1] <= 1, name="policy_no_joint_A_B")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, "STATUS_" + str(model.Status))

if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(round(value)) for value in values]
    raw_objective = float(model.ObjVal)
    objective = raw_objective if math.isfinite(raw_objective) else None

    checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[2] + values[4], ">=", 1.0),
        (values[1] + values[3] + values[5], ">=", 1.0),
        (values[0] + values[1] + values[2], ">=", 2.0),
        (values[0] + values[1], "<=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
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
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
