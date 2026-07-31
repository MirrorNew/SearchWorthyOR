import gurobipy as gp
import json
import math

# [VARIABLES]
model = gp.Model("SWOR001_patched")
model.Params.OutputFlag = 0
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

# [OBJECTIVE]
benefits = [1015, 954, 912, 851, 790, 748]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

# [C_MAX_MODES]
model.addConstr(gp.quicksum(x) <= 3, name="max_enabled_modes")

# [C_CAPACITY]
capacity = [4, 1, 2, 3, 4, 1]
model.addConstr(gp.quicksum(capacity[i] * x[i] for i in range(6)) <= 7, name="capacity_limit")

# [C_BASE_EF]
model.addConstr(x[4] + x[5] <= 1, name="baseline_conflict_E_F")

# [C_POLICY_AB]
model.addConstr(x[0] + x[1] <= 1, name="policy_conflict_A_B")

# [SOLVE_OUTPUT]
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
    values = [v.X for v in x]
    projected_action = [int(round(value)) for value in values]
    violations = [
        max(0.0, sum(values) - 3.0),
        max(0.0, sum(capacity[i] * values[i] for i in range(6)) - 7.0),
        max(0.0, values[4] + values[5] - 1.0),
        max(0.0, values[0] + values[1] - 1.0)
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
else:
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))