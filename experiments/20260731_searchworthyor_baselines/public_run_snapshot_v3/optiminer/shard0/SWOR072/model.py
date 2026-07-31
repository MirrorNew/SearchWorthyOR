import gurobipy
import json
import math

model = gurobipy.Model("SWOR072_patched")
model.Params.OutputFlag = 0
x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

benefits = [1004, 962, 901, 859, 798, 737, 695, 634]
model.setObjective(gurobipy.quicksum(benefits[i] * x[i] for i in range(8)), gurobipy.GRB.MAXIMIZE)

model.addConstr(gurobipy.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="cover_period_1")
model.addConstr(x[1] + x[4] + x[7] >= 1, name="cover_period_2")
model.addConstr(x[2] + x[5] >= 1, name="cover_period_3")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_abc_at_least_2")
model.addConstr(x[0] + x[1] <= 1, name="policy_A_excludes_B")

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
    projected_action = [int(v >= 0.5) for v in values]
    checks = [
        ("==", sum(values), 3.0),
        (">=", values[0] + values[3] + values[6], 1.0),
        (">=", values[1] + values[4] + values[7], 1.0),
        (">=", values[2] + values[5], 1.0),
        (">=", values[0] + values[1] + values[2], 2.0),
        ("<=", values[0] + values[1], 1.0)
    ]
    violations = []
    for sense, lhs, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": float(max(violations)),
        "integrality_violation": float(max(abs(v - round(v)) for v in values))
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0, 0, 0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))