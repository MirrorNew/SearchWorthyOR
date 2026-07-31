import gurobipy as gp
import json

model = gp.Model("SWOR069_patched")
model.Params.OutputFlag = 0
model.Params.Threads = 1
model.Params.Seed = 0
model.Params.PoolSearchMode = 2
model.Params.PoolSolutions = 64

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
utilities = [1017, 956, 895, 853, 792, 750]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="required_assignment_count")
model.addConstr(x[0] + x[3] <= 1, name="conflict_resource_1_A_D")
model.addConstr(x[1] + x[4] <= 1, name="conflict_resource_2_B_E")
model.addConstr(x[2] + x[5] <= 1, name="conflict_resource_3_C_F")
model.addConstr(x[1] + x[4] + x[5] == 1, name="core_choice_B_E_F")

# POLICY PATCH: DOC-BD60DC8FC60AF7CF
model.addConstr(x[0] - x[4] - x[5] <= 0, name="policy_8h_break_link")

model.optimize()

if model.Status == gp.GRB.OPTIMAL:
    status = "OPTIMAL"
elif model.Status == gp.GRB.INFEASIBLE:
    status = "INFEASIBLE"
elif model.Status == gp.GRB.INF_OR_UNBD:
    status = "INF_OR_UNBD"
elif model.Status == gp.GRB.UNBOUNDED:
    status = "UNBOUNDED"
else:
    status = "STATUS_" + str(model.Status)

result = {
    "status": status,
    "objective": None,
    "projected_action": None,
    "max_constraint_violation": None,
    "integrality_violation": None,
    "all_optimal_projected_actions": []
}

if model.SolCount > 0:
    raw = [v.X for v in x]
    projected = [int(round(value)) for value in raw]
    result["objective"] = float(model.ObjVal)
    result["projected_action"] = projected

    constraint_specs = [
        ("==", 3.0, {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1}),
        ("<=", 1.0, {0: 1, 3: 1}),
        ("<=", 1.0, {1: 1, 4: 1}),
        ("<=", 1.0, {2: 1, 5: 1}),
        ("==", 1.0, {1: 1, 4: 1, 5: 1}),
        ("<=", 0.0, {0: 1, 4: -1, 5: -1})
    ]
    violations = [max(0.0, -value, value - 1.0) for value in raw]
    for sense, rhs, terms in constraint_specs:
        lhs = sum(coef * raw[index] for index, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    result["max_constraint_violation"] = float(max(violations))
    result["integrality_violation"] = float(max(abs(value - round(value)) for value in raw))

    if model.Status == gp.GRB.OPTIMAL:
        best_objective = model.ObjVal
        optimal_actions = []
        for solution_number in range(model.SolCount):
            model.Params.SolutionNumber = solution_number
            if abs(model.PoolObjVal - best_objective) <= 1e-6:
                action = [int(round(v.Xn)) for v in x]
                if action not in optimal_actions:
                    optimal_actions.append(action)
        result["all_optimal_projected_actions"] = sorted(optimal_actions)

print(json.dumps(result, ensure_ascii=False, sort_keys=True))
