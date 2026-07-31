import gurobipy as gp
from gurobipy import GRB
import json
import math

NAMES = ["A", "B", "C", "D", "E", "F"]
UTILITY = [1015, 954, 912, 851, 790, 748]

model = gp.Model("SWOR012_patched")
model.Params.OutputFlag = 0
model.Params.PoolSearchMode = 2
model.Params.PoolSolutions = 64
model.Params.PoolGap = 0.0
model.Params.Seed = 0

x = [model.addVar(vtype=GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}") for i in range(6)]
model.setObjective(gp.quicksum(UTILITY[i] * x[i] for i in range(6)), GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="base_exactly_three")
model.addConstr(x[0] + x[1] >= 1, name="base_emergency_coverage")
model.addConstr(x[1] + x[2] >= 1, name="base_continuity_coverage")
model.addConstr(x[0] + x[2] >= 1, name="base_specialty_coverage")
model.addConstr(x[0] + x[3] >= 1, name="base_primary_or_backup")
model.addConstr(x[0] + x[1] <= 1, name="patch_no_180_day_path_when_A_triggers_LQG")
model.addConstr(x[0] - x[4] - x[5] <= 0, name="patch_LQG_requires_registered_90_day_capacity")

constraint_specs = [
    ("==", 3.0, {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1}),
    (">=", 1.0, {0: 1, 1: 1}),
    (">=", 1.0, {1: 1, 2: 1}),
    (">=", 1.0, {0: 1, 2: 1}),
    (">=", 1.0, {0: 1, 3: 1}),
    ("<=", 1.0, {0: 1, 1: 1}),
    ("<=", 0.0, {0: 1, 4: -1, 5: -1})
]

model.optimize()
status_names = {
    GRB.OPTIMAL: "OPTIMAL",
    GRB.INFEASIBLE: "INFEASIBLE",
    GRB.INF_OR_UNBD: "INF_OR_UNBD",
    GRB.UNBOUNDED: "UNBOUNDED",
    GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.Status == GRB.OPTIMAL:
    values = [var.X for var in x]
    projected_action = [int(value >= 0.5) for value in values]
    objective = float(model.ObjVal)

    violations = []
    for sense, rhs, terms in constraint_specs:
        lhs = sum(coef * values[index] for index, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(math.fabs(lhs - rhs))
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))

    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(math.fabs(value - round(value)) for value in values)

    optimal_actions = []
    for solution_number in range(model.SolCount):
        model.Params.SolutionNumber = solution_number
        if math.fabs(model.PoolObjVal - objective) <= 1e-6:
            action = [int(var.Xn >= 0.5) for var in x]
            if action not in optimal_actions:
                optimal_actions.append(action)
    optimal_actions.sort()
    optimal_action_names = [[NAMES[i] for i, enabled in enumerate(action) if enabled] for action in optimal_actions]
else:
    objective = None
    projected_action = [0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None
    optimal_actions = []
    optimal_action_names = []

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
    "optimal_actions": optimal_actions,
    "optimal_action_names": optimal_action_names,
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))