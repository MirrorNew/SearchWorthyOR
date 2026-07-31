import gurobipy as gp
import json
import math

# REGION: VARIABLES
model = gp.Model("SWOR029_patched")
model.Params.OutputFlag = 0
names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}
model.update()

# REGION: OBJECTIVE
profits = {
    "x_0": 1015, "x_1": 954, "x_2": 912, "x_3": 851,
    "x_4": 790, "x_5": 748, "x_6": 687, "x_7": 645
}
model.setObjective(gp.quicksum(profits[name] * x[name] for name in names), gp.GRB.MAXIMIZE)

# REGION: BASE_SEGMENT_1
model.addConstr(x["x_0"] + x["x_3"] + x["x_6"] == 1, name="segment_1_exactly_one")
# REGION: BASE_SEGMENT_2
model.addConstr(x["x_1"] + x["x_4"] + x["x_7"] == 1, name="segment_2_exactly_one")
# REGION: BASE_SEGMENT_3
model.addConstr(x["x_2"] + x["x_5"] == 1, name="segment_3_exactly_one")
# REGION: BASE_CORE_REQUIREMENT
model.addConstr(x["x_0"] + x["x_1"] + x["x_2"] >= 2, name="core_abc_at_least_two")
# REGION: POLICY_GUARANTEE_DOC_1A2832290453125F
model.addConstr(x["x_6"] + x["x_7"] >= 1, name="guarantee_option_at_least_one")

# REGION: SOLVE
model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, "STATUS_" + str(model.Status))

# REGION: VALIDATION_AND_OUTPUT
if model.SolCount > 0:
    values = {name: float(x[name].X) for name in names}
    projected_action = [int(round(values[name])) for name in names]
    objective = float(model.ObjVal)
    if not math.isfinite(objective):
        objective = None

    rows = [
        ({"x_0": 1, "x_3": 1, "x_6": 1}, "==", 1),
        ({"x_1": 1, "x_4": 1, "x_7": 1}, "==", 1),
        ({"x_2": 1, "x_5": 1}, "==", 1),
        ({"x_0": 1, "x_1": 1, "x_2": 1}, ">=", 2),
        ({"x_6": 1, "x_7": 1}, ">=", 1)
    ]
    violations = []
    for terms, sense, rhs in rows:
        lhs = sum(coef * values[name] for name, coef in terms.items())
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(values[name] - round(values[name])) for name in names)
else:
    objective = None
    projected_action = None
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
