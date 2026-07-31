import gurobipy
import json
import math

model = gurobipy.Model("SWOR023")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
values = [1012, 951, 909, 848, 806, 745, 684]
model.setObjective(gurobipy.quicksum(values[i] * x[i] for i in range(7)), gurobipy.GRB.MAXIMIZE)

model.addConstr(gurobipy.quicksum(x) == 3, name="activate_exactly_3")
model.addConstr(x[0] + x[1] >= 1, name="emergency_coverage")
model.addConstr(x[1] + x[2] >= 1, name="continuous_care_coverage")
model.addConstr(x[0] + x[2] >= 1, name="specialty_coverage")
# Evidence DOC-CBCBD22409439B8D: service unit A is ineligible.
model.addConstr(x[0] == 0, name="policy_A_ineligible")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
    gurobipy.GRB.INTERRUPTED: "INTERRUPTED"
}
result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": None,
    "projected_action": [],
    "max_constraint_violation": None,
    "integrality_violation": None
}

if model.SolCount > 0:
    vals = [var.X for var in x]
    result["objective"] = float(model.ObjVal)
    result["projected_action"] = [int(round(v)) for v in vals]

    rows = [
        (sum(vals), "==", 3.0),
        (vals[0] + vals[1], ">=", 1.0),
        (vals[1] + vals[2], ">=", 1.0),
        (vals[0] + vals[2], ">=", 1.0),
        (vals[0], "==", 0.0)
    ]
    violations = []
    for lhs, sense, rhs in rows:
        if sense == "==":
            violations.append(math.fabs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    for value in vals:
        violations.append(max(0.0, -value, value - 1.0))
    result["max_constraint_violation"] = max(violations)
    result["integrality_violation"] = max(math.fabs(v - round(v)) for v in vals)

print(json.dumps(result, ensure_ascii=False, allow_nan=False))
