import gurobipy as gp
import json
import math

m = gp.Model("SWOR022")
m.Params.OutputFlag = 0

x = [m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
m.setObjective(1006*x[0] + 964*x[1] + 903*x[2] + 842*x[3] + 800*x[4] + 739*x[5], gp.GRB.MAXIMIZE)

m.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
m.addConstr(x[0] + x[1] + x[3] >= 1, name="front_segment_at_least_one")
m.addConstr(x[1] + x[2] + x[4] >= 1, name="back_segment_at_least_one")
m.addConstr(x[1] + x[4] + x[5] == 1, name="core_backup_emergency_exactly_one")

m.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(m.Status, str(m.Status))

if m.SolCount > 0:
    values = [v.X for v in x]
    projected_action = [int(round(value)) for value in values]
    violations = [
        abs(sum(values) - 3),
        max(0.0, 1 - (values[0] + values[1] + values[3])),
        max(0.0, 1 - (values[1] + values[2] + values[4])),
        abs(values[1] + values[4] + values[5] - 1)
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = m.ObjVal
else:
    projected_action = [0, 0, 0, 0, 0, 0]
    objective = None
    max_constraint_violation = 3.0
    integrality_violation = 0.0

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))