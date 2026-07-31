import gurobipy
import json
import math

model = gurobipy.Model("SWOR028")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
model.update()

benefits = [1013, 952, 910, 849, 788, 746, 685, 643]
model.setObjective(gurobipy.quicksum(benefits[i] * x[i] for i in range(8)), gurobipy.GRB.MAXIMIZE)

model.addConstr(gurobipy.quicksum(x) == 3, name="build_exactly_3")
model.addConstr(x[0] + x[2] + x[4] + x[6] >= 1, name="service_area_1_coverage")
model.addConstr(x[1] + x[3] + x[5] + x[7] >= 1, name="service_area_2_coverage")
model.addConstr(x[6] + x[7] <= 1, name="terminal_backup_mutual_exclusion")

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
    values = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in values]
    lhs_values = [
        sum(values),
        values[0] + values[2] + values[4] + values[6],
        values[1] + values[3] + values[5] + values[7],
        values[6] + values[7]
    ]
    violations = [
        abs(lhs_values[0] - 3.0),
        max(0.0, 1.0 - lhs_values[1]),
        max(0.0, 1.0 - lhs_values[2]),
        max(0.0, lhs_values[3] - 1.0)
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in values)
    objective = float(model.ObjVal)
else:
    projected_action = [0 for _ in range(8)]
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
print(json.dumps(result, ensure_ascii=False))