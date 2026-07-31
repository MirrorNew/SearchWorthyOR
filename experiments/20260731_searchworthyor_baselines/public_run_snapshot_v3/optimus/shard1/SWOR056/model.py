import gurobipy
import json
import math

model = gurobipy.Model("SWOR056_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
benefits = [1002, 960, 899, 857, 796, 735, 693, 632]
x = {name: model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

model.setObjective(
    gurobipy.quicksum(benefits[i] * x[names[i]] for i in range(len(names))),
    gurobipy.GRB.MAXIMIZE
)

model.addConstr(gurobipy.quicksum(x[name] for name in names) == 3, name="exactly_three_packages")
model.addConstr(x["x_0"] + x["x_1"] + x["x_3"] + x["x_6"] >= 1, name="front_segment_minimum")
model.addConstr(x["x_1"] + x["x_2"] + x["x_4"] + x["x_7"] >= 1, name="back_segment_minimum")
model.addConstr(x["x_6"] + x["x_7"] <= 1, name="base_conflict_G_H")
model.addConstr(x["x_0"] + x["x_1"] <= 1, name="external_conflict_A_B")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [x[name].X for name in names]
    projected_action = [int(value >= 0.5) for value in values]
    objective = model.ObjVal

    checks = [
        (sum(values), "==", 3),
        (values[0] + values[1] + values[3] + values[6], ">=", 1),
        (values[1] + values[2] + values[4] + values[7], ">=", 1),
        (values[6] + values[7], "<=", 1),
        (values[0] + values[1], "<=", 1)
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
    integrality_violation = max(min(abs(value), abs(value - 1.0)) for value in values)
else:
    objective = None
    projected_action = []
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
