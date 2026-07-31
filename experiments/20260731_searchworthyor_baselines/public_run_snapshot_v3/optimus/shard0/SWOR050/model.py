import gurobipy as gp
import json
import math

model = gp.Model("SWOR050_patched")
model.Params.OutputFlag = 0

x = [
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}")
    for i in range(6)
]

benefits = [1007, 965, 904, 843, 801, 740]
model.setObjective(
    gp.quicksum(benefits[i] * x[i] for i in range(6)),
    gp.GRB.MAXIMIZE,
)

model.addConstr(gp.quicksum(x) <= 3, name="maximum_activated_units")
model.addConstr(
    2*x[0] + 3*x[1] + 4*x[2] + x[3] + 2*x[4] + 3*x[5] <= 9,
    name="maximum_grid_resource_usage",
)
model.addConstr(x[0] + x[3] >= 1, name="minimum_clean_capability")
model.addConstr(x[1] + x[4] >= 1, name="minimum_reserve_capability")
model.addConstr(x[0] + x[3] >= 1, name="minimum_core_alternative")

# DOC-9E7B5FF9625AA0CB is the uniquely applicable policy.
model.addConstr(x[0] == 0, name="policy_plan_A_ineligible")

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
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    violations = [
        max(0.0, sum(values) - 3.0),
        max(0.0, 2*values[0] + 3*values[1] + 4*values[2] + values[3] + 2*values[4] + 3*values[5] - 9.0),
        max(0.0, 1.0 - values[0] - values[3]),
        max(0.0, 1.0 - values[1] - values[4]),
        max(0.0, 1.0 - values[0] - values[3]),
        abs(values[0]),
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal)
else:
    projected_action = [0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
