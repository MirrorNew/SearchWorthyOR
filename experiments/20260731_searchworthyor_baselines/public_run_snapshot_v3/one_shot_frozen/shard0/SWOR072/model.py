import gurobipy as gp
import json
import math

model = gp.Model("SWOR072")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
benefits = [1004, 962, 901, 859, 798, 737, 695, 634]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="cover_period_1")
model.addConstr(x[1] + x[4] + x[7] >= 1, name="cover_period_2")
model.addConstr(x[2] + x[5] >= 1, name="cover_period_3")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_candidates_min_2")
model.addConstr(x[0] + x[1] <= 1, name="regulatory_A_excludes_B")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw = [float(v.X) for v in x]
    projected_action = [int(round(value)) for value in raw]
    objective = float(model.ObjVal)
    lhs_values = [
        sum(raw),
        raw[0] + raw[3] + raw[6],
        raw[1] + raw[4] + raw[7],
        raw[2] + raw[5],
        raw[0] + raw[1] + raw[2],
        raw[0] + raw[1]
    ]
    violations = [
        abs(lhs_values[0] - 3.0),
        max(0.0, 1.0 - lhs_values[1]),
        max(0.0, 1.0 - lhs_values[2]),
        max(0.0, 1.0 - lhs_values[3]),
        max(0.0, 2.0 - lhs_values[4]),
        max(0.0, lhs_values[5] - 1.0)
    ]
    max_constraint_violation = float(max(violations))
    integrality_violation = float(max(abs(value - round(value)) for value in raw))
else:
    projected_action = [0 for _ in range(8)]
    objective = None
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))