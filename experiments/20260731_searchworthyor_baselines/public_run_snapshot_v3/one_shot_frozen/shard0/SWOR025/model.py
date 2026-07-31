import gurobipy
import json
import math

model = gurobipy.Model("SWOR025_patched")
model.Params.OutputFlag = 0
model.Params.PoolSearchMode = 2
model.Params.PoolSolutions = 128

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name="x_" + str(i)) for i in range(7)]
profits = [1006, 964, 903, 842, 800, 739, 697]
model.setObjective(gurobipy.quicksum(profits[i] * x[i] for i in range(7)), gurobipy.GRB.MAXIMIZE)

model.addConstr(gurobipy.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="cover_period_1")
model.addConstr(x[1] + x[4] >= 1, name="cover_period_2")
model.addConstr(x[2] + x[5] >= 1, name="cover_period_3")
model.addConstr(x[5] + x[6] <= 1, name="reserve_F_G_mutex")
model.addConstr(x[0] + x[1] <= 1, name="policy_A_implies_not_B")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))
objective = None
projected_action = []
optimal_projected_actions = []
max_constraint_violation = None
integrality_violation = None

if model.Status == gurobipy.GRB.OPTIMAL:
    objective = float(model.ObjVal)
    for solution_number in range(model.SolCount):
        model.Params.SolutionNumber = solution_number
        if math.fabs(float(model.PoolObjVal) - objective) <= 1e-6:
            candidate = [int(round(x[i].Xn)) for i in range(7)]
            if candidate not in optimal_projected_actions:
                optimal_projected_actions.append(candidate)
    optimal_projected_actions.sort(reverse=True)
    projected_action = optimal_projected_actions[0]

    checks = [
        (sum(projected_action), "==", 3),
        (projected_action[0] + projected_action[3] + projected_action[6], ">=", 1),
        (projected_action[1] + projected_action[4], ">=", 1),
        (projected_action[2] + projected_action[5], ">=", 1),
        (projected_action[5] + projected_action[6], "<=", 1),
        (projected_action[0] + projected_action[1], "<=", 1)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "<=":
            violations.append(max(0.0, float(lhs - rhs)))
        elif sense == ">=":
            violations.append(max(0.0, float(rhs - lhs)))
        else:
            violations.append(math.fabs(float(lhs - rhs)))
    for value in projected_action:
        violations.append(max(0.0, -float(value), float(value) - 1.0))
    max_constraint_violation = max(violations)
    integrality_violation = max(math.fabs(float(value) - round(float(value))) for value in projected_action)

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "optimal_projected_actions": optimal_projected_actions,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))