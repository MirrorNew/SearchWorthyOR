import gurobipy
import json
import math

model = gurobipy.Model("SWOR029_patched")
model.Params.OutputFlag = 0

benefit = [1015.0, 954.0, 912.0, 851.0, 790.0, 748.0, 687.0, 645.0]
x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}") for i in range(8)]

model.setObjective(gurobipy.quicksum(benefit[i] * x[i] for i in range(8)), gurobipy.GRB.MAXIMIZE)
model.addConstr(x[0] + x[3] + x[6] == 1, name="segment_1_exactly_one")
model.addConstr(x[1] + x[4] + x[7] == 1, name="segment_2_exactly_one")
model.addConstr(x[2] + x[5] == 1, name="segment_3_exactly_one")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="minimum_core_packages")
model.addConstr(x[6] + x[7] >= 1, name="policy_minimum_safeguard")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in raw]
    objective = float(model.ObjVal)
    checks = [
        (raw[0] + raw[3] + raw[6], "==", 1.0),
        (raw[1] + raw[4] + raw[7], "==", 1.0),
        (raw[2] + raw[5], "==", 1.0),
        (raw[0] + raw[1] + raw[2], ">=", 2.0),
        (raw[6] + raw[7], ">=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(rhs - lhs, 0.0))
        else:
            violations.append(max(lhs - rhs, 0.0))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in raw)
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0, 0]
    objective = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))