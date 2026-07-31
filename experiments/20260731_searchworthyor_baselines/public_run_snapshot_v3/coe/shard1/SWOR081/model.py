import gurobipy as gp
import json

model = gp.Model("SWOR081_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

profits = [1017, 956, 895, 853, 792, 750, 689, 647]
x = model.addVars(8, vtype=gp.GRB.BINARY, lb=0, ub=1, name="x")
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x[i] for i in range(8)) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[1] >= 1, name="emergency_coverage")
model.addConstr(x[1] + x[2] >= 1, name="continuity_coverage")
model.addConstr(x[0] + x[2] >= 1, name="specialty_coverage")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_at_least_2")
model.addConstr(x[0] + x[1] <= 1, name="policy_ab_mutex")

model.optimize()

if model.Status == gp.GRB.OPTIMAL:
    values = [float(x[i].X) for i in range(8)]
    projected_action = [int(values[i] >= 0.5) for i in range(8)]
    checks = [
        ([1, 1, 1, 1, 1, 1, 1, 1], "==", 3),
        ([1, 1, 0, 0, 0, 0, 0, 0], ">=", 1),
        ([0, 1, 1, 0, 0, 0, 0, 0], ">=", 1),
        ([1, 0, 1, 0, 0, 0, 0, 0], ">=", 1),
        ([1, 1, 1, 0, 0, 0, 0, 0], ">=", 2),
        ([1, 1, 0, 0, 0, 0, 0, 0], "<=", 1)
    ]
    violations = []
    for coefficients, sense, rhs in checks:
        lhs = sum(coefficients[i] * values[i] for i in range(8))
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    result = {
        "status": "OPTIMAL",
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(value - round(value)) for value in values)
    }
else:
    result = {
        "status": str(int(model.Status)),
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, sort_keys=True))
