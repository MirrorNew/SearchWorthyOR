import gurobipy as gp
import json
import math

# REGION_VARIABLES
model = gp.Model("SWOR036")
model.Params.OutputFlag = 0
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

# REGION_OBJECTIVE
mode_values = [1009, 948, 906, 845, 803, 742]
model.setObjective(
    gp.quicksum(mode_values[i] * x[i] for i in range(6)),
    gp.GRB.MAXIMIZE,
)

# REGION_BASE_CONSTRAINTS
model.addConstr(gp.quicksum(x) <= 3, name="maximum_enabled_modes")
capacity_use = [1, 2, 3, 4, 1, 2]
model.addConstr(
    gp.quicksum(capacity_use[i] * x[i] for i in range(6)) <= 6,
    name="equipment_capacity",
)
model.addConstr(x[1] + x[4] + x[5] == 1, name="exactly_one_B_E_F")

# REGION_EVIDENCE_PATCH_DOC_E77927F9FA0CA366
model.addConstr(x[0] == 0, name="mode_A_ineligible")

# REGION_SOLVE_AND_REPORT
model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
}
status = status_names.get(model.Status, str(model.Status))
has_solution = model.SolCount > 0
raw_action = [float(v.X) for v in x] if has_solution else [0.0] * 6
projected_action = [int(v >= 0.5) for v in raw_action]

if has_solution:
    objective = float(model.ObjVal)
    if not math.isfinite(objective):
        objective = None
    constraint_violations = [
        max(0.0, sum(raw_action) - 3.0),
        max(0.0, sum(capacity_use[i] * raw_action[i] for i in range(6)) - 6.0),
        abs(raw_action[1] + raw_action[4] + raw_action[5] - 1.0),
        abs(raw_action[0]),
    ]
    bound_violations = [max(0.0, -v, v - 1.0) for v in raw_action]
    max_constraint_violation = max(constraint_violations + bound_violations)
    integrality_violation = max(abs(v - round(v)) for v in raw_action)
else:
    objective = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
