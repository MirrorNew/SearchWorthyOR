import gurobipy as gp
import json
import math

model = gp.Model("SWOR075")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
model.update()

benefits = [1015, 954, 912, 851, 790, 748, 687]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="build_exactly_3")
model.addConstr(x[0] + x[2] + x[4] + x[6] >= 1, name="cover_service_area_1")
model.addConstr(x[1] + x[3] + x[5] >= 1, name="cover_service_area_2")

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
    raw = [v.X for v in x]
    projected_action = [int(round(value)) for value in raw]
    violations = [
        abs(sum(raw) - 3.0),
        max(0.0, 1.0 - (raw[0] + raw[2] + raw[4] + raw[6])),
        max(0.0, 1.0 - (raw[1] + raw[3] + raw[5]))
    ]
    violations.extend(max(0.0, -value, value - 1.0) for value in raw)
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in raw)
    objective = float(model.ObjVal)
else:
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
