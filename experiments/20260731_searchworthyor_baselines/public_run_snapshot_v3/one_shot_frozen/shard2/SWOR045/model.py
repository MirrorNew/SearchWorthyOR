import gurobipy as gp
import json
import math

model = gp.Model("SWOR045_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

model.setObjective(
    1009 * x[0] + 948 * x[1] + 906 * x[2] + 845 * x[3]
    + 803 * x[4] + 742 * x[5] + 700 * x[6],
    gp.GRB.MAXIMIZE,
)

model.addConstr(gp.quicksum(x) == 3, name="build_exactly_three")
model.addConstr(x[0] + x[2] + x[4] + x[6] >= 1, name="cover_service_area_1")
model.addConstr(x[1] + x[3] + x[5] >= 1, name="cover_service_area_2")
model.addConstr(x[0] + x[3] >= 1, name="core_or_backup")
model.addConstr(x[0] + x[1] <= 1, name="compliance_A_excludes_B")

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
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    violations = [
        abs(sum(values) - 3),
        max(0.0, 1 - (values[0] + values[2] + values[4] + values[6])),
        max(0.0, 1 - (values[1] + values[3] + values[5])),
        max(0.0, 1 - (values[0] + values[3])),
        max(0.0, values[0] + values[1] - 1),
    ]
    result = {
        "status": status,
        "objective": model.ObjVal,
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
