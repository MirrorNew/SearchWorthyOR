import gurobipy as gp
import json
import math

model = gp.Model("SWOR087_patched")
model.Params.OutputFlag = 0

x = [
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_0"),
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_1"),
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_2"),
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_3"),
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_4"),
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_5"),
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_6"),
]

benefit = [1007, 965, 904, 843, 801, 740, 698]
capacity = [4, 1, 2, 3, 4, 1, 2]

model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x[i] for i in range(7)) <= 3, name="c_mode_count")
model.addConstr(gp.quicksum(capacity[i] * x[i] for i in range(7)) <= 7, name="c_device_capacity")
model.addConstr(x[0] + x[1] <= 1, name="c_external_ab_mutex")

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
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    violations = [
        max(0.0, sum(values) - 3.0),
        max(0.0, sum(capacity[i] * values[i] for i in range(7)) - 7.0),
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
        "projected_action": [0, 0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None,
    }

print(json.dumps(result, ensure_ascii=False))