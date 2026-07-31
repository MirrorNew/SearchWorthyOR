import gurobipy as gp
import json
import math

model = gp.Model("SWOR028_patched")
model.Params.OutputFlag = 0

benefits = [1013, 952, 910, 849, 788, 746, 685, 643]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[2] + x[4] + x[6] >= 1, name="service_area_1_coverage")
model.addConstr(x[1] + x[3] + x[5] + x[7] >= 1, name="service_area_2_coverage")
model.addConstr(x[6] + x[7] <= 1, name="g_h_mutual_exclusion")
model.addConstr(x[6] + x[7] >= 1, name="safeguard_requirement")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(v >= 0.5) for v in values]
    integrality_violation = max(abs(v - round(v)) for v in values)

    checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[2] + values[4] + values[6], ">=", 1.0),
        (values[1] + values[3] + values[5] + values[7], ">=", 1.0),
        (values[6] + values[7], "<=", 1.0),
        (values[6] + values[7], ">=", 1.0)
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
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": integrality_violation
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