import gurobipy as gp
import json
import math

model = gp.Model("SWOR100_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
benefits = {
    "x_0": 1005,
    "x_1": 963,
    "x_2": 902,
    "x_3": 841,
    "x_4": 799,
    "x_5": 738
}
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

model.setObjective(gp.quicksum(benefits[name] * x[name] for name in names), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x[name] for name in names) == 3, name="facility_count")
model.addConstr(x["x_0"] + x["x_2"] + x["x_4"] >= 1, name="service_area_1_coverage")
model.addConstr(x["x_1"] + x["x_3"] + x["x_5"] >= 1, name="service_area_2_coverage")
model.addConstr(x["x_0"] == 0, name="policy_node_A_ineligible")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [x[name].X for name in names]
    projected_action = [int(round(value)) for value in values]
    integrality_violation = max(abs(value - round(value)) for value in values)

    violations = []
    violations.append(abs(sum(values) - 3.0))
    violations.append(max(0.0, 1.0 - (values[0] + values[2] + values[4])))
    violations.append(max(0.0, 1.0 - (values[1] + values[3] + values[5])))
    violations.append(abs(values[0]))
    for value in values:
        violations.append(max(0.0, -value))
        violations.append(max(0.0, value - 1.0))

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
        "projected_action": [0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))
