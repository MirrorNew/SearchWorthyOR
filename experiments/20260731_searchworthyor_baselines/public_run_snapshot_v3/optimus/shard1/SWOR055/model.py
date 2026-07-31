import gurobipy as gp
import json
import math

model = gp.Model("SWOR055_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
utilities = [1013, 952, 910, 849, 788, 746, 685]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="enabled_unit_count")
model.addConstr(x[0] + x[1] >= 1, name="emergency_coverage")
model.addConstr(x[1] + x[2] >= 1, name="continuity_coverage")
model.addConstr(x[0] + x[2] >= 1, name="specialty_coverage")
model.addConstr(x[1] + x[4] + x[6] == 1, name="exclusive_B_E_G")
model.addConstr(x[5] + x[6] >= 1, name="federal_mercury_compliance")

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
    values = [v.X for v in x]
    projected_action = [int(value >= 0.5) for value in values]
    integrality_violation = max(abs(value - round(value)) for value in values)
    checks = [
        (sum(values), "==", 3),
        (values[0] + values[1], ">=", 1),
        (values[1] + values[2], ">=", 1),
        (values[0] + values[2], ">=", 1),
        (values[1] + values[4] + values[6], "==", 1),
        (values[5] + values[6], ">=", 1)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
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
        "projected_action": None,
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))