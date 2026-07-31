import gurobipy as gp
import json
import math

model = gp.Model("SWOR052_patched")
model.Params.OutputFlag = 0

names = ["匹配A", "匹配B", "匹配C", "匹配D", "匹配E", "匹配F", "匹配G", "匹配H"]
utilities = [1006, 964, 903, 842, 800, 739, 697, 636]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="c_exactly_three")
model.addConstr(x[0] + x[3] + x[6] <= 1, name="c_subject_1_at_most_one")
model.addConstr(x[1] + x[4] + x[7] <= 1, name="c_subject_2_at_most_one")
model.addConstr(x[2] + x[5] <= 1, name="c_subject_3_at_most_one")
model.addConstr(x[6] + x[7] >= 1, name="c_policy_protection_min")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [v.X for v in x]
    projected = [int(round(v)) for v in values]
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, values[0] + values[3] + values[6] - 1.0),
        max(0.0, values[1] + values[4] + values[7] - 1.0),
        max(0.0, values[2] + values[5] - 1.0),
        max(0.0, 1.0 - values[6] - values[7])
    ]
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected,
        "selected_actions": [names[i] for i, value in enumerate(projected) if value == 1],
        "max_constraint_violation": float(max(violations)),
        "integrality_violation": float(max(abs(v - round(v)) for v in values))
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [],
        "selected_actions": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))