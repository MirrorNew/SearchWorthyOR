import gurobipy as gp
import json
import math

model = gp.Model("SWOR081")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
benefits = [1017, 956, 895, 853, 792, 750, 689, 647]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[1] >= 1, name="emergency_A_or_B")
model.addConstr(x[1] + x[2] >= 1, name="continuity_B_or_C")
model.addConstr(x[0] + x[2] >= 1, name="specialty_A_or_C")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_at_least_2")
model.addConstr(x[0] + x[1] <= 1, name="policy_A_B_mutex")

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
    projected_action = [1 if value >= 0.5 else 0 for value in values]
    objective = float(model.ObjVal)

    specifications = [
        ([1, 1, 1, 1, 1, 1, 1, 1], "==", 3),
        ([1, 1, 0, 0, 0, 0, 0, 0], ">=", 1),
        ([0, 1, 1, 0, 0, 0, 0, 0], ">=", 1),
        ([1, 0, 1, 0, 0, 0, 0, 0], ">=", 1),
        ([1, 1, 1, 0, 0, 0, 0, 0], ">=", 2),
        ([1, 1, 0, 0, 0, 0, 0, 0], "<=", 1)
    ]
    violations = []
    for coefficients, sense, rhs in specifications:
        lhs = sum(coefficients[i] * values[i] for i in range(8))
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    objective = None
    projected_action = [0, 0, 0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
