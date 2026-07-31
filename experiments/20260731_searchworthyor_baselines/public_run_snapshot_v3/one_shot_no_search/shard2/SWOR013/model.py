import gurobipy as gp
import json
import math

model = gp.Model("SWOR013")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
utilities = [1000, 958, 897, 855, 794, 752, 691, 630]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]

model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="complete_exactly_three")
model.addConstr(x[0] + x[3] + x[6] <= 1, name="resource_subject_1_at_most_one")
model.addConstr(x[1] + x[4] + x[7] <= 1, name="resource_subject_2_at_most_one")
model.addConstr(x[2] + x[5] <= 1, name="resource_subject_3_at_most_one")
model.addConstr(x[0] + x[3] >= 1, name="match_A_or_D_at_least_one")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw = [var.X for var in x]
    projected = [int(round(value)) for value in raw]
    objective = float(model.ObjVal)
    violations = [
        abs(sum(raw) - 3.0),
        max(0.0, raw[0] + raw[3] + raw[6] - 1.0),
        max(0.0, raw[1] + raw[4] + raw[7] - 1.0),
        max(0.0, raw[2] + raw[5] - 1.0),
        max(0.0, 1.0 - raw[0] - raw[3])
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in raw)
else:
    projected = [0 for _ in names]
    objective = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
