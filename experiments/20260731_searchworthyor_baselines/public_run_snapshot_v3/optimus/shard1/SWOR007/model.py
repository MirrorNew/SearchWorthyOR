import gurobipy
import json
import math

model = gurobipy.Model("SWOR007_patched")
model.Params.OutputFlag = 0
model.Params.PoolSearchMode = 2
model.Params.PoolSolutions = 10
model.Params.PoolGap = 0.0

profits = [1013, 952, 910, 849, 788, 746]
x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}") for i in range(6)]

model.setObjective(gurobipy.quicksum(profits[i] * x[i] for i in range(6)), gurobipy.GRB.MAXIMIZE)
model.addConstr(x[0] + x[3] == 1, name="segment_1_exactly_one")
model.addConstr(x[1] + x[4] == 1, name="segment_2_exactly_one")
model.addConstr(x[2] + x[5] == 1, name="segment_3_exactly_one")
model.addConstr(x[0] + x[3] >= 1, name="core_alternative_minimum")
model.addConstr(x[4] + x[5] >= 1, name="applicable_guarantee_minimum")

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
    violations = [
        abs(values[0] + values[3] - 1.0),
        abs(values[1] + values[4] - 1.0),
        abs(values[2] + values[5] - 1.0),
        max(0.0, 1.0 - values[0] - values[3]),
        max(0.0, 1.0 - values[4] - values[5])
    ]
    violations.extend(max(0.0, -value, value - 1.0) for value in values)
    integrality_violation = max(abs(value - round(value)) for value in values)
    optimal_actions = set()
    if model.Status == gurobipy.GRB.OPTIMAL:
        optimum = float(model.ObjVal)
        for solution_number in range(model.SolCount):
            model.Params.SolutionNumber = solution_number
            if math.isclose(float(model.PoolObjVal), optimum, rel_tol=0.0, abs_tol=1e-6):
                optimal_actions.add(tuple(int(v.Xn >= 0.5) for v in x))
    if not optimal_actions:
        optimal_actions.add(tuple(projected_action))
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "optimal_projected_actions": [list(action) for action in sorted(optimal_actions)],
        "max_constraint_violation": float(max(violations)),
        "integrality_violation": float(integrality_violation)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [],
        "optimal_projected_actions": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, sort_keys=True))
