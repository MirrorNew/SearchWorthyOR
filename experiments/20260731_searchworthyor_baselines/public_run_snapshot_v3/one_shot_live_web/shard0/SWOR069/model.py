import gurobipy as gp
import json
import math

model = gp.Model("SWOR069_patched")
model.Params.OutputFlag = 0
model.Params.PoolSearchMode = 2
model.Params.PoolSolutions = 64
model.Params.PoolGap = 0.0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
objective_coefficients = [1017, 956, 895, 853, 792, 750]
model.setObjective(gp.quicksum(objective_coefficients[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

rows = [
    ("frozen_exactly_3", "==", 3.0, {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0}),
    ("resource_subject_1_at_most_1", "<=", 1.0, {0: 1.0, 3: 1.0}),
    ("resource_subject_2_at_most_1", "<=", 1.0, {1: 1.0, 4: 1.0}),
    ("resource_subject_3_at_most_1", "<=", 1.0, {2: 1.0, 5: 1.0}),
    ("frozen_core_exactly_1", "==", 1.0, {1: 1.0, 4: 1.0, 5: 1.0}),
    ("hos_30min_break_dependency", "<=", 0.0, {0: 1.0, 4: -1.0, 5: -1.0})
]

for name, sense, rhs, terms in rows:
    lhs = gp.quicksum(coefficient * x[index] for index, coefficient in terms.items())
    if sense == "<=":
        model.addConstr(lhs <= rhs, name=name)
    elif sense == ">=":
        model.addConstr(lhs >= rhs, name=name)
    else:
        model.addConstr(lhs == rhs, name=name)

model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD"
}
result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": None,
    "projected_action": [],
    "max_constraint_violation": None,
    "integrality_violation": None,
    "optimal_projected_actions": []
}

if model.SolCount > 0:
    optimum = float(model.ObjVal)
    solution_pairs = []
    seen = []
    for solution_number in range(model.SolCount):
        model.Params.SolutionNumber = solution_number
        raw = [float(variable.Xn) for variable in x]
        action = [int(value >= 0.5) for value in raw]
        action_objective = float(sum(objective_coefficients[i] * action[i] for i in range(6)))
        if abs(action_objective - optimum) <= 1e-6 and action not in seen:
            seen.append(action)
            solution_pairs.append((action, raw))
    solution_pairs.sort(key=lambda pair: pair[0])
    projected_action, raw_values = solution_pairs[0]
    violations = []
    for name, sense, rhs, terms in rows:
        lhs_value = sum(coefficient * raw_values[index] for index, coefficient in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs_value - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs_value))
        else:
            violations.append(abs(lhs_value - rhs))
    result["objective"] = optimum
    result["projected_action"] = projected_action
    result["max_constraint_violation"] = float(max(violations))
    result["integrality_violation"] = float(max(abs(value - round(value)) for value in raw_values))
    result["optimal_projected_actions"] = [pair[0] for pair in solution_pairs]

print(json.dumps(result, ensure_ascii=False, allow_nan=False))