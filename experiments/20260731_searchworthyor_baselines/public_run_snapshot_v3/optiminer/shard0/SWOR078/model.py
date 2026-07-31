import gurobipy as gp
import json
import math

model = gp.Model("SWOR078_patched")
model.Params.OutputFlag = 0

# [VARIABLES]
x_0 = model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_0")
x_1 = model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_1")
x_2 = model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_2")
x_3 = model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_3")
x_4 = model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_4")
x_5 = model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_5")
action_projection = [x_0, x_1, x_2, x_3, x_4, x_5]

# [OBJECTIVE]
model.setObjective(
    1017 * x_0 + 956 * x_1 + 895 * x_2 + 853 * x_3 + 792 * x_4 + 750 * x_5,
    gp.GRB.MAXIMIZE,
)

# [C_BASE_COUNT]
model.addConstr(x_0 + x_1 + x_2 + x_3 + x_4 + x_5 <= 3, name="c_base_module_limit")
# [C_BASE_ZONE1]
model.addConstr(x_0 + x_3 >= 1, name="c_base_zone1")
# [C_BASE_ZONE2]
model.addConstr(x_1 + x_4 >= 1, name="c_base_zone2")
# [C_BASE_ZONE3]
model.addConstr(x_2 + x_5 >= 1, name="c_base_zone3")
# [C_BASE_A_BACKHAUL]
model.addConstr(-x_0 + x_1 + x_4 >= 0, name="c_base_A_requires_B_or_E")
# [C_BASE_MUTEX]
model.addConstr(x_4 + x_5 <= 1, name="c_base_E_F_mutex")
# [C_POLICY_GUARANTEE]
model.addConstr(x_4 + x_5 >= 1, name="c_policy_guarantee_option")
# [NO_RESOURCE_CAP] No aggregate resource-budget RHS was stated or established by applicable evidence.

# [SOLVE_AND_REPORT]
model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, "STATUS_" + str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in action_projection]
    projected_action = [int(round(value)) for value in values]
    checks = [
        (sum(values), "<=", 3.0),
        (values[0] + values[3], ">=", 1.0),
        (values[1] + values[4], ">=", 1.0),
        (values[2] + values[5], ">=", 1.0),
        (-values[0] + values[1] + values[4], ">=", 0.0),
        (values[4] + values[5], "<=", 1.0),
        (values[4] + values[5], ">=", 1.0),
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal)
    if not math.isfinite(objective):
        objective = None
else:
    objective = None
    projected_action = [0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None

output = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(output, ensure_ascii=False, allow_nan=False))
