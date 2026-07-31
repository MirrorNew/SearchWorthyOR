import gurobipy as gp
import json
import math

model = gp.Model("SWOR023")
model.Params.OutputFlag = 0

values = [1012, 951, 909, 848, 806, 745, 684]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

model.setObjective(gp.quicksum(values[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="enable_exactly_3_units")
model.addConstr(x[0] + x[1] >= 1, name="emergency_coverage_A_or_B")
model.addConstr(x[1] + x[2] >= 1, name="continuity_coverage_B_or_C")
model.addConstr(x[0] + x[2] >= 1, name="specialty_coverage_A_or_C")

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
    raw = [float(v.X) for v in x]
    projected_action = [int(v >= 0.5) for v in raw]
    violations = [
        abs(sum(raw) - 3.0),
        max(0.0, 1.0 - raw[0] - raw[1]),
        max(0.0, 1.0 - raw[1] - raw[2]),
        max(0.0, 1.0 - raw[0] - raw[2])
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in raw)
    objective = float(model.ObjVal)
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0]
    max_constraint_violation = math.inf
    integrality_violation = math.inf
    objective = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False, allow_nan=True))