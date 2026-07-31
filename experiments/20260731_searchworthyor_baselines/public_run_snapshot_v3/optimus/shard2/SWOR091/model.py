import gurobipy as gp
import json
import math

model = gp.Model("SWOR091_patched")
model.Params.OutputFlag = 0
model.Params.PoolSearchMode = 2
model.Params.PoolSolutions = 100
model.Params.PoolGap = 0.0

# REGION_VARIABLES
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
model.update()

# REGION_OBJECTIVE
benefits = [1014, 953, 911, 850, 789, 747]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

# REGION_BASE_CONSTRAINTS
model.addConstr(gp.quicksum(x) == 3, name="required_shift_count")
model.addConstr(x[0] + x[3] >= 1, name="timeslot_1_coverage")
model.addConstr(x[1] + x[4] >= 1, name="timeslot_2_coverage")
model.addConstr(x[2] + x[5] >= 1, name="timeslot_3_coverage")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="minimum_core_shifts")

# REGION_POLICY_PATCH: DOC-B0B955449052FC7F
model.addConstr(x[0] + x[1] <= 1, name="policy_ab_mutual_exclusion")

model.optimize()

# REGION_SOLUTION_REPORTING
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))
objective = None
projected_action = []
optimal_actions = []
max_constraint_violation = None
integrality_violation = None

if model.Status == gp.GRB.OPTIMAL:
    best_objective = float(model.ObjVal)
    optimal_by_action = {}
    for solution_number in range(model.SolCount):
        model.Params.SolutionNumber = solution_number
        pool_objective = float(model.PoolObjVal)
        if math.isclose(pool_objective, best_objective, rel_tol=0.0, abs_tol=1e-6):
            raw_values = [float(var.Xn) for var in x]
            action = tuple(int(round(value)) for value in raw_values)
            optimal_by_action[action] = raw_values

    if not optimal_by_action:
        raw_values = [float(var.X) for var in x]
        action = tuple(int(round(value)) for value in raw_values)
        optimal_by_action[action] = raw_values

    ordered_actions = sorted(optimal_by_action.keys(), reverse=True)
    representative = ordered_actions[0]
    representative_raw = optimal_by_action[representative]
    projected_action = list(representative)
    optimal_actions = [list(action) for action in ordered_actions]
    objective = best_objective

    constraint_specs = [
        ("==", 3.0, [1, 1, 1, 1, 1, 1]),
        (">=", 1.0, [1, 0, 0, 1, 0, 0]),
        (">=", 1.0, [0, 1, 0, 0, 1, 0]),
        (">=", 1.0, [0, 0, 1, 0, 0, 1]),
        (">=", 2.0, [1, 1, 1, 0, 0, 0]),
        ("<=", 1.0, [1, 1, 0, 0, 0, 0])
    ]
    violations = []
    for sense, rhs, coefficients in constraint_specs:
        lhs = sum(coefficients[i] * representative_raw[i] for i in range(6))
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in representative_raw)

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "optimal_actions": optimal_actions,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))