import gurobipy as gp
import json
import math

model = gp.Model("SWOR025_patched")
model.Params.OutputFlag = 0
model.Params.PoolSearchMode = 2
model.Params.PoolSolutions = 128
model.Params.PoolGap = 0.0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

objective_terms = [1006, 964, 903, 842, 800, 739, 697]
model.setObjective(gp.quicksum(objective_terms[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="cover_period_1")
model.addConstr(x[1] + x[4] >= 1, name="cover_period_2")
model.addConstr(x[2] + x[5] >= 1, name="cover_period_3")
model.addConstr(x[5] + x[6] <= 1, name="reserve_F_G_mutex")
model.addConstr(x[0] + x[1] <= 1, name="policy_A_excludes_B")

model.optimize()

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
projected_action = None
max_constraint_violation = None
integrality_violation = None
optimal_actions = []

if model.SolCount > 0:
    raw = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in raw]
    objective = float(model.ObjVal)
    if not math.isfinite(objective):
        objective = None

    violations = [
        abs(sum(raw) - 3.0),
        max(0.0, 1.0 - (raw[0] + raw[3] + raw[6])),
        max(0.0, 1.0 - (raw[1] + raw[4])),
        max(0.0, 1.0 - (raw[2] + raw[5])),
        max(0.0, raw[5] + raw[6] - 1.0),
        max(0.0, raw[0] + raw[1] - 1.0)
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in raw)

    if model.Status == gp.GRB.OPTIMAL:
        seen = set()
        for solution_number in range(model.SolCount):
            model.Params.SolutionNumber = solution_number
            candidate = tuple(int(round(v.Xn)) for v in x)
            candidate_objective = float(model.PoolObjVal)
            if abs(candidate_objective - float(model.ObjVal)) <= 1e-6 and candidate not in seen:
                seen.add(candidate)
                optimal_actions.append(list(candidate))
        optimal_actions.sort()

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "optimal_actions": optimal_actions,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
