import gurobipy as gp
import json
import math

model = gp.Model("SWOR045_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

model.setObjective(
    1009 * x["x_0"] + 948 * x["x_1"] + 906 * x["x_2"]
    + 845 * x["x_3"] + 803 * x["x_4"] + 742 * x["x_5"]
    + 700 * x["x_6"],
    gp.GRB.MAXIMIZE,
)

model.addConstr(gp.quicksum(x[name] for name in names) == 3, name="build_exactly_3")
model.addConstr(x["x_0"] + x["x_2"] + x["x_4"] + x["x_6"] >= 1, name="cover_service_area_1")
model.addConstr(x["x_1"] + x["x_3"] + x["x_5"] >= 1, name="cover_service_area_2")
model.addConstr(x["x_0"] + x["x_3"] >= 1, name="core_A_or_backup_D")
model.addConstr(x["x_0"] + x["x_1"] <= 1, name="ext_A_excludes_B")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(x[name].X) for name in names]
    projected_action = [int(round(value)) for value in values]
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, 1.0 - (values[0] + values[2] + values[4] + values[6])),
        max(0.0, 1.0 - (values[1] + values[3] + values[5])),
        max(0.0, 1.0 - (values[0] + values[3])),
        max(0.0, values[0] + values[1] - 1.0),
    ]
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(value - round(value)) for value in values),
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": None,
        "max_constraint_violation": None,
        "integrality_violation": None,
    }

print(json.dumps(result, ensure_ascii=False))
