import gurobipy as gp
import json
import math

model = gp.Model("SWOR039_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0
model.Params.PoolSearchMode = 2
model.Params.PoolSolutions = 100
model.Params.PoolGap = 0.0

# REGION variables
names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
semantic_names = ["路径包A", "路径包B", "路径包C", "路径包D", "路径包E", "路径包F", "路径包G"]
x = {
    name: model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=name)
    for name in names
}
model.update()

# REGION objective
objective_coefficients = {
    "x_0": 1005, "x_1": 963, "x_2": 902, "x_3": 841,
    "x_4": 799, "x_5": 738, "x_6": 696
}
model.setObjective(
    gp.quicksum(objective_coefficients[name] * x[name] for name in names),
    gp.GRB.MAXIMIZE,
)

# REGION base_constraints
model.addConstr(x["x_0"] + x["x_3"] + x["x_6"] == 1, name="segment_1_exactly_one")
model.addConstr(x["x_1"] + x["x_4"] == 1, name="segment_2_exactly_one")
model.addConstr(x["x_2"] + x["x_5"] == 1, name="segment_3_exactly_one")
model.addConstr(x["x_0"] + x["x_1"] + x["x_2"] >= 2, name="core_abc_at_least_two")

# REGION policy_constraint_DOC_9E36C576EC024BEB
model.addConstr(x["x_0"] + x["x_1"] <= 1, name="compliance_a_excludes_b")

# REGION solve_and_report
model.optimize()

constraint_rows = [
    ({"x_0": 1, "x_3": 1, "x_6": 1}, "==", 1),
    ({"x_1": 1, "x_4": 1}, "==", 1),
    ({"x_2": 1, "x_5": 1}, "==", 1),
    ({"x_0": 1, "x_1": 1, "x_2": 1}, ">=", 2),
    ({"x_0": 1, "x_1": 1}, "<=", 1),
]

def violations(values):
    result = []
    for terms, sense, rhs in constraint_rows:
        lhs = sum(coef * values[names.index(name)] for name, coef in terms.items())
        if sense == "==":
            result.append(abs(lhs - rhs))
        elif sense == "<=":
            result.append(max(0.0, lhs - rhs))
        else:
            result.append(max(0.0, rhs - lhs))
    return result

if model.Status == gp.GRB.OPTIMAL and model.SolCount > 0:
    optimum = float(model.ObjVal)
    solution_records = {}
    for solution_number in range(model.SolCount):
        model.Params.SolutionNumber = solution_number
        pool_objective = float(model.PoolObjVal)
        if abs(pool_objective - optimum) <= 1e-6:
            raw = [float(x[name].Xn) for name in names]
            action = tuple(int(round(value)) for value in raw)
            solution_records[action] = raw

    if not solution_records:
        raw = [float(x[name].X) for name in names]
        solution_records[tuple(int(round(value)) for value in raw)] = raw

    ordered_actions = sorted(solution_records.keys(), reverse=True)
    selected_action = ordered_actions[0]
    selected_raw = solution_records[selected_action]
    max_violation = max(violations(selected_raw))
    integrality_violation = max(abs(value - round(value)) for value in selected_raw)
    reported_objective = optimum if math.isfinite(optimum) else None
    output = {
        "status": "OPTIMAL",
        "objective": reported_objective,
        "projected_action": list(selected_action),
        "optimal_actions": [list(action) for action in ordered_actions],
        "max_constraint_violation": float(max_violation),
        "integrality_violation": float(integrality_violation),
    }
else:
    output = {
        "status": str(model.Status),
        "objective": None,
        "projected_action": [],
        "optimal_actions": [],
        "max_constraint_violation": None,
        "integrality_violation": None,
    }

print(json.dumps(output, ensure_ascii=False, sort_keys=True))