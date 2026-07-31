import gurobipy as gp
import json
import math

model = gp.Model("SWOR011_patched")
model.Params.OutputFlag = 0

x = model.addVars(6, vtype=gp.GRB.BINARY, lb=0, ub=1, name="x")
utilities = [1016, 955, 894, 852, 791, 749]

model.setObjective(
    gp.quicksum(utilities[i] * x[i] for i in range(6)),
    gp.GRB.MAXIMIZE,
)

model.addConstr(gp.quicksum(x[i] for i in range(6)) == 3, name="required_selection_count")
model.addConstr(x[0] + x[3] <= 1, name="mutex_resource_subject_1")
model.addConstr(x[1] + x[4] <= 1, name="mutex_resource_subject_2")
model.addConstr(x[2] + x[5] <= 1, name="mutex_resource_subject_3")
model.addConstr(x[0] <= 0, name="policy_ineligible_match_A")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
}
result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": None,
    "projected_action": None,
    "max_constraint_violation": None,
    "integrality_violation": None,
}

if model.SolCount > 0:
    values = [float(x[i].X) for i in range(6)]
    projected_action = [int(round(value)) for value in values]
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, values[0] + values[3] - 1.0),
        max(0.0, values[1] + values[4] - 1.0),
        max(0.0, values[2] + values[5] - 1.0),
        max(0.0, values[0]),
    ]
    for value in values:
        violations.append(max(0.0, -value))
        violations.append(max(0.0, value - 1.0))
    result["objective"] = float(model.ObjVal)
    result["projected_action"] = projected_action
    result["max_constraint_violation"] = float(max(violations))
    result["integrality_violation"] = float(max(abs(value - round(value)) for value in values))

print(json.dumps(result, ensure_ascii=False, allow_nan=False))