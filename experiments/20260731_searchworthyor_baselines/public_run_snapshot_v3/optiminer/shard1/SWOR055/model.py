import gurobipy
import json
import math

model = gurobipy.Model("SWOR055")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
utilities = [1013, 952, 910, 849, 788, 746, 685]
model.setObjective(gurobipy.quicksum(utilities[i] * x[i] for i in range(7)), gurobipy.GRB.MAXIMIZE)

model.addConstr(gurobipy.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[1] >= 1, name="emergency_cover")
model.addConstr(x[1] + x[2] >= 1, name="continuity_cover")
model.addConstr(x[0] + x[2] >= 1, name="specialty_cover")
model.addConstr(x[1] + x[4] + x[6] == 1, name="core_backup_terminal_exactly_1")
# PATCH DOC-AE16A54CFEDAC082：至少启用F或G，使汞浓度由180降至110，不超过130。
model.addConstr(x[5] + x[6] >= 1, name="mercury_compliance")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))
has_solution = model.SolCount > 0

if has_solution:
    raw_action = [x[i].X for i in range(7)]
    projected_action = [int(round(value)) for value in raw_action]
    integrality_violation = max(abs(value - round(value)) for value in raw_action)
    checks = [
        (sum(raw_action), "==", 3.0),
        (raw_action[0] + raw_action[1], ">=", 1.0),
        (raw_action[1] + raw_action[2], ">=", 1.0),
        (raw_action[0] + raw_action[2], ">=", 1.0),
        (raw_action[1] + raw_action[4] + raw_action[6], "==", 1.0),
        (raw_action[5] + raw_action[6], ">=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    max_constraint_violation = max(violations)
    objective = model.ObjVal
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0]
    integrality_violation = None
    max_constraint_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))