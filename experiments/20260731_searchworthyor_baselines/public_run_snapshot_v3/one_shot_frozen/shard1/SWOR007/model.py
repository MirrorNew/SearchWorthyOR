import gurobipy as gp
import json

m = gp.Model("SWOR007_patched")
m.Params.OutputFlag = 0
m.Params.PoolSearchMode = 2
m.Params.PoolSolutions = 64
m.Params.PoolGap = 0.0

x = [m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
objective_coefficients = [1013, 952, 910, 849, 788, 746]
m.setObjective(gp.quicksum(objective_coefficients[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

m.addConstr(x[0] + x[3] == 1, name="segment_1_exactly_one")
m.addConstr(x[1] + x[4] == 1, name="segment_2_exactly_one")
m.addConstr(x[2] + x[5] == 1, name="segment_3_exactly_one")
m.addConstr(x[0] + x[3] >= 1, name="core_A_D_at_least_one")
m.addConstr(x[4] + x[5] >= 1, name="policy_safeguard_E_F_at_least_one")

constraint_data = [
    ({0: 1, 3: 1}, "==", 1),
    ({1: 1, 4: 1}, "==", 1),
    ({2: 1, 5: 1}, "==", 1),
    ({0: 1, 3: 1}, ">=", 1),
    ({4: 1, 5: 1}, ">=", 1)
]

m.optimize()
status_labels = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_labels.get(m.Status, str(m.Status))
projected_action = [0, 0, 0, 0, 0, 0]
objective = None
max_constraint_violation = None
integrality_violation = None
alternative_optimal_actions = []

if m.SolCount > 0:
    best_objective = m.ObjVal
    candidates = []
    for solution_number in range(m.SolCount):
        m.Params.SolutionNumber = solution_number
        raw_values = [x[i].Xn for i in range(6)]
        candidate_objective = sum(objective_coefficients[i] * raw_values[i] for i in range(6))
        if abs(candidate_objective - best_objective) <= 1e-6:
            action = tuple(1 if value >= 0.5 else 0 for value in raw_values)
            candidates.append((action, raw_values, candidate_objective))

    if not candidates:
        raw_values = [x[i].X for i in range(6)]
        action = tuple(1 if value >= 0.5 else 0 for value in raw_values)
        candidate_objective = sum(objective_coefficients[i] * raw_values[i] for i in range(6))
        candidates.append((action, raw_values, candidate_objective))

    candidates.sort(key=lambda item: item[0])
    selected_action, selected_raw_values, objective = candidates[0]
    projected_action = list(selected_action)
    alternative_optimal_actions = [list(action) for action in sorted(set(item[0] for item in candidates))]

    violations = []
    for terms, sense, rhs in constraint_data:
        lhs = sum(coefficient * selected_raw_values[index] for index, coefficient in terms.items())
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in selected_raw_values)

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
    "alternative_optimal_actions": alternative_optimal_actions
}
print(json.dumps(result, ensure_ascii=False))
