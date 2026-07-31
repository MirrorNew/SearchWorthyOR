import gurobipy as gp
import json
import math

model = gp.Model("SWOR056_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}
model.update()

benefit = {
    "x_0": 1002, "x_1": 960, "x_2": 899, "x_3": 857,
    "x_4": 796, "x_5": 735, "x_6": 693, "x_7": 632
}
model.setObjective(gp.quicksum(benefit[name] * x[name] for name in names), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x[name] for name in names) == 3, name="frozen_select_exactly_three")
model.addConstr(x["x_0"] + x["x_1"] + x["x_3"] + x["x_6"] >= 1, name="front_segment_supply")
model.addConstr(x["x_1"] + x["x_2"] + x["x_4"] + x["x_7"] >= 1, name="rear_segment_supply")
model.addConstr(x["x_6"] + x["x_7"] <= 1, name="terminal_backups_mutual_exclusion")
model.addConstr(x["x_0"] + x["x_1"] <= 1, name="policy_no_joint_A_B")

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
    values = [x[name].X for name in names]
    projected_action = [int(round(value)) for value in values]
    total = sum(values)
    front = values[0] + values[1] + values[3] + values[6]
    rear = values[1] + values[2] + values[4] + values[7]
    backups = values[6] + values[7]
    policy_pair = values[0] + values[1]
    violations = [
        abs(total - 3.0),
        max(0.0, 1.0 - front),
        max(0.0, 1.0 - rear),
        max(0.0, backups - 1.0),
        max(0.0, policy_pair - 1.0)
    ]
    integrality_violation = max(abs(value - round(value)) for value in values)
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))
