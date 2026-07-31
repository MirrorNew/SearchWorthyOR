import gurobipy as gp
import json
import math

model = gp.Model("SWOR049_patched")
model.Params.OutputFlag = 0

x = [
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}")
    for i in range(6)
]

objective_coefficients = [1003, 961, 900, 858, 797, 736]
model.setObjective(
    gp.quicksum(objective_coefficients[i] * x[i] for i in range(6)),
    gp.GRB.MAXIMIZE,
)

model.addConstr(gp.quicksum(x) == 3, name="c_position_count")
model.addConstr(x[0] + 2*x[1] + 3*x[2] + 4*x[3] + x[4] + 2*x[5] <= 12, name="c_capital_limit")
model.addConstr(5*x[0] + 2*x[1] + 4*x[2] + x[3] + 3*x[4] + 5*x[5] <= 15, name="c_risk_limit")
model.addConstr(x[1] + x[4] + x[5] == 1, name="c_B_E_F_exactly_one")
model.addConstr(x[0] + x[1] <= 1, name="c_policy_A_implies_not_B")

model.optimize()

status_names = {
    1: "LOADED",
    2: "OPTIMAL",
    3: "INFEASIBLE",
    4: "INF_OR_UNBD",
    5: "UNBOUNDED",
    9: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw_values = [float(var.X) for var in x]
    projected_action = [int(value >= 0.5) for value in raw_values]
    objective = float(model.ObjVal)

    diagnostic_constraints = [
        ([1, 1, 1, 1, 1, 1], "==", 3),
        ([1, 2, 3, 4, 1, 2], "<=", 12),
        ([5, 2, 4, 1, 3, 5], "<=", 15),
        ([0, 1, 0, 0, 1, 1], "==", 1),
        ([1, 1, 0, 0, 0, 0], "<=", 1),
    ]
    violations = []
    for coefficients, sense, rhs in diagnostic_constraints:
        lhs = sum(coefficients[i] * raw_values[i] for i in range(6))
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))

    max_constraint_violation = max(violations)
    integrality_violation = max(
        abs(value - round(value)) for value in raw_values
    )
else:
    objective = None
    projected_action = [0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
