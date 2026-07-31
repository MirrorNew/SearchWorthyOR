import gurobipy as gp
import json

ir = {
    "sense": "max",
    "variables": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1017, "x_1": 956, "x_2": 895, "x_3": 853, "x_4": 792, "x_5": 750}
    },
    "constraints": [
        {"name": "frozen_assignment_count", "sense": "==", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}},
        {"name": "subject_1_exclusivity", "sense": "<=", "rhs": 1, "terms": {"x_0": 1, "x_3": 1}},
        {"name": "subject_2_exclusivity", "sense": "<=", "rhs": 1, "terms": {"x_1": 1, "x_4": 1}},
        {"name": "subject_3_exclusivity", "sense": "<=", "rhs": 1, "terms": {"x_2": 1, "x_5": 1}},
        {"name": "core_backup_emergency_exactly_one", "sense": "==", "rhs": 1, "terms": {"x_1": 1, "x_4": 1, "x_5": 1}},
        {"name": "hos_30min_break_link", "sense": "<=", "rhs": 0, "terms": {"x_0": 1, "x_4": -1, "x_5": -1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
}

model = gp.Model("SWOR069_patched")
model.Params.OutputFlag = 0
model.Params.Threads = 1
model.Params.Seed = 0
model.Params.PoolSearchMode = 2
model.Params.PoolSolutions = 20
model.Params.PoolGap = 0

x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in ir["variables"]}
objective = ir["objective"]["constant"] + gp.quicksum(coef * x[name] for name, coef in ir["objective"]["terms"].items())
model.setObjective(objective, gp.GRB.MAXIMIZE)

for constraint in ir["constraints"]:
    lhs = gp.quicksum(coef * x[name] for name, coef in constraint["terms"].items())
    if constraint["sense"] == "<=":
        model.addConstr(lhs <= constraint["rhs"], name=constraint["name"])
    elif constraint["sense"] == ">=":
        model.addConstr(lhs >= constraint["rhs"], name=constraint["name"])
    else:
        model.addConstr(lhs == constraint["rhs"], name=constraint["name"])

model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    best_objective = model.ObjVal
    optimal_actions = []
    for solution_number in range(model.SolCount):
        model.Params.SolutionNumber = solution_number
        if abs(model.PoolObjVal - best_objective) <= 1e-6:
            action = [int(round(x[name].Xn)) for name in ir["action_projection"]]
            if action not in optimal_actions:
                optimal_actions.append(action)
    optimal_actions.sort()
    projected_action = optimal_actions[0]
    values = dict(zip(ir["action_projection"], projected_action))
    objective_value = ir["objective"]["constant"] + sum(coef * values[name] for name, coef in ir["objective"]["terms"].items())
    violations = []
    for constraint in ir["constraints"]:
        lhs_value = sum(coef * values[name] for name, coef in constraint["terms"].items())
        if constraint["sense"] == "<=":
            violation = max(0.0, lhs_value - constraint["rhs"])
        elif constraint["sense"] == ">=":
            violation = max(0.0, constraint["rhs"] - lhs_value)
        else:
            violation = abs(lhs_value - constraint["rhs"])
        violations.append(violation)
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values.values())
else:
    objective_value = None
    projected_action = []
    optimal_actions = []
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective_value,
    "projected_action": projected_action,
    "all_optimal_actions": optimal_actions,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))