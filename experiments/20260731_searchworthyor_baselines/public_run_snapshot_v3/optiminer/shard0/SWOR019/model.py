import gurobipy as gp
import json
import math

model = gp.Model("SWOR019_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

model.setObjective(
    1011 * x["x_0"] + 950 * x["x_1"] + 908 * x["x_2"]
    + 847 * x["x_3"] + 805 * x["x_4"] + 744 * x["x_5"]
    + 683 * x["x_6"],
    gp.GRB.MAXIMIZE,
)

model.addConstr(gp.quicksum(x[name] for name in names) <= 3, name="unit_count_limit")
model.addConstr(4*x["x_0"] + x["x_1"] + 2*x["x_2"] + 3*x["x_3"] + 4*x["x_4"] + x["x_5"] + 2*x["x_6"] <= 7, name="grid_resource_limit")
model.addConstr(x["x_0"] + x["x_3"] + x["x_6"] >= 1, name="clean_capability_min")
model.addConstr(x["x_1"] + x["x_4"] >= 1, name="backup_capability_min")
model.addConstr(x["x_5"] + x["x_6"] <= 1, name="terminal_backup_mutex")
model.addConstr(x["x_5"] + x["x_6"] >= 1, name="external_guarantee_min")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [x[name].X for name in names]
    projected_action = [int(round(value)) for value in values]
    lhs_count = sum(values)
    lhs_resource = 4*values[0] + values[1] + 2*values[2] + 3*values[3] + 4*values[4] + values[5] + 2*values[6]
    violations = [
        max(0.0, lhs_count - 3.0),
        max(0.0, lhs_resource - 7.0),
        max(0.0, 1.0 - (values[0] + values[3] + values[6])),
        max(0.0, 1.0 - (values[1] + values[4])),
        max(0.0, values[5] + values[6] - 1.0),
        max(0.0, 1.0 - (values[5] + values[6])),
    ]
    for value in values:
        violations.extend([max(0.0, -value), max(0.0, value - 1.0)])
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
else:
    objective = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}, ensure_ascii=False))
