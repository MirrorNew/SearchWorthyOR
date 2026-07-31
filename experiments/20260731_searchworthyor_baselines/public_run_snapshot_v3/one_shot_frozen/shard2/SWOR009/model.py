import gurobipy
import json

model = gurobipy.Model("SWOR009_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

profits = [1018, 957, 896, 854, 793, 751, 690, 629]
capital = [3, 4, 1, 2, 3, 4, 1, 2]
risk = [2, 4, 1, 3, 5, 2, 4, 1]

model.setObjective(gurobipy.quicksum(profits[i] * x[i] for i in range(8)), gurobipy.GRB.MAXIMIZE)
model.addConstr(gurobipy.quicksum(x) == 3, name="position_count_eq_3")
model.addConstr(gurobipy.quicksum(capital[i] * x[i] for i in range(8)) <= 12, name="capital_limit")
model.addConstr(gurobipy.quicksum(risk[i] * x[i] for i in range(8)) <= 15, name="risk_limit")
model.addConstr(x[6] + x[7] <= 1, name="backup_mutual_exclusion")
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
    projected_action = [int(value >= 0.5) for value in values]
    objective = float(model.ObjVal)

    checks = [
        (sum(values), "==", 3.0),
        (sum(capital[i] * values[i] for i in range(8)), "<=", 12.0),
        (sum(risk[i] * values[i] for i in range(8)), "<=", 15.0),
        (values[6] + values[7], "<=", 1.0),
        (values[0] + values[1], "<=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = float(max(violations))
    integrality_violation = float(max(abs(value - round(value)) for value in values))
else:
    objective = None
    projected_action = [0] * 8
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