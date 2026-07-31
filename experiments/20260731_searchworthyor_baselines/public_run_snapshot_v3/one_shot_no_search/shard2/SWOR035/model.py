import gurobipy
import json
import math

model = gurobipy.Model("SWOR035")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

benefits = [1017, 956, 895, 853, 792, 750, 689]
model.setObjective(gurobipy.quicksum(benefits[i] * x[i] for i in range(7)), gurobipy.GRB.MAXIMIZE)

model.addConstr(gurobipy.quicksum(x) == 3, name="select_exactly_three_blocks")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="front_segment_at_least_one")
model.addConstr(x[1] + x[2] + x[4] >= 1, name="back_segment_at_least_one")
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_backup_D")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [x[i].X for i in range(7)]
    projected_action = [int(round(value)) for value in values]
    violations = [
        abs(sum(values) - 3),
        max(0.0, 1.0 - (values[0] + values[1] + values[3] + values[6])),
        max(0.0, 1.0 - (values[1] + values[2] + values[4])),
        max(0.0, 1.0 - (values[0] + values[3]))
    ]
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))
    integrality_violation = max(abs(value - round(value)) for value in values)
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))
