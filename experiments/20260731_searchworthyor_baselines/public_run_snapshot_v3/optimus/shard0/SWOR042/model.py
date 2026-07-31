import gurobipy as gp
import json
import math

model = gp.Model("SWOR042")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
utilities = [1002, 960, 899, 857, 796, 735]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

model.setObjective(gp.quicksum(utilities[i] * x[names[i]] for i in range(6)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x[name] for name in names) == 3, name="enabled_shift_count")
model.addConstr(x["x_0"] + x["x_3"] >= 1, name="time_slot_1_coverage")
model.addConstr(x["x_1"] + x["x_4"] >= 1, name="time_slot_2_coverage")
model.addConstr(x["x_2"] + x["x_5"] >= 1, name="time_slot_3_coverage")
model.addConstr(x["x_0"] + x["x_3"] >= 1, name="core_A_or_D")
model.addConstr(x["x_0"] + x["x_1"] <= 1, name="flsa_meal_standby_incompatibility")

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
    values = [float(x[name].X) for name in names]
    projected_action = [int(round(value)) for value in values]
    integrality_violation = max(abs(value - round(value)) for value in values)

    violations = []
    violations.append(abs(sum(values) - 3.0))
    violations.append(max(0.0, 1.0 - (values[0] + values[3])))
    violations.append(max(0.0, 1.0 - (values[1] + values[4])))
    violations.append(max(0.0, 1.0 - (values[2] + values[5])))
    violations.append(max(0.0, 1.0 - (values[0] + values[3])))
    violations.append(max(0.0, values[0] + values[1] - 1.0))
    max_constraint_violation = max(violations)
    objective = float(model.ObjVal)
else:
    projected_action = []
    integrality_violation = None
    max_constraint_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
