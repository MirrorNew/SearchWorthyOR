import gurobipy as gp
import json
import math

model = gp.Model("SWOR100_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

model.setObjective(
    1005 * x[0] + 963 * x[1] + 902 * x[2] +
    841 * x[3] + 799 * x[4] + 738 * x[5],
    gp.GRB.MAXIMIZE
)

model.addConstr(gp.quicksum(x) == 3, name="build_exactly_three")
model.addConstr(x[0] + x[2] + x[4] >= 1, name="service_area_1_coverage")
model.addConstr(x[1] + x[3] + x[5] >= 1, name="service_area_2_coverage")
model.addConstr(x[0] == 0, name="policy_node_A_ineligible")

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
    values = [var.X for var in x]
    projected_action = [int(value >= 0.5) for value in values]
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, 1.0 - (values[0] + values[2] + values[4])),
        max(0.0, 1.0 - (values[1] + values[3] + values[5])),
        abs(values[0])
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal if math.isfinite(model.ObjVal) else None
else:
    objective = None
    projected_action = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
