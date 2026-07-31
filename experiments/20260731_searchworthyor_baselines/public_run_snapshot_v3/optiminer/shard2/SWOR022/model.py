import gurobipy as gp
import json
import math

model = gp.Model("SWOR022")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

benefits = [1006, 964, 903, 842, 800, 739]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[1] + x[3] >= 1, name="front_segment_cover")
model.addConstr(x[1] + x[2] + x[4] >= 1, name="back_segment_cover")
model.addConstr(x[1] + x[4] + x[5] == 1, name="core_backup_emergency_exactly_1")
model.addConstr(x[0] == 0, name="eligibility_A")

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
    values = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in values]
    integrality_violation = max(abs(v - round(v)) for v in values)

    checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[1] + values[3], ">=", 1.0),
        (values[1] + values[2] + values[4], ">=", 1.0),
        (values[1] + values[4] + values[5], "==", 1.0),
        (values[0], "==", 0.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))

    result = {
        "status": status,
        "objective": float(model.ObjVal),
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

print(json.dumps(result, ensure_ascii=False))