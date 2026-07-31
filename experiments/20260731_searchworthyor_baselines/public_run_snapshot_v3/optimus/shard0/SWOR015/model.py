import gurobipy as gp
import json
import math

model = gp.Model("SWOR015")
model.Params.OutputFlag = 0

# SLOT variables.package_selection
x = [
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}")
    for i in range(6)
]

# SLOT objective.total_supply_benefit
benefits = [1012, 951, 909, 848, 806, 745]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

# SLOT constraints.required_package_count
model.addConstr(gp.quicksum(x) == 3, name="required_package_count")

# SLOT constraints.front_stage_minimum
model.addConstr(x[0] + x[1] + x[3] >= 1, name="front_stage_minimum")

# SLOT constraints.frozen_back_stage_minimum
model.addConstr(x[1] + x[2] + x[4] >= 1, name="frozen_back_stage_minimum")

# SLOT constraints.local_E_F_mutual_exclusion
model.addConstr(x[4] + x[5] <= 1, name="local_E_F_mutual_exclusion")

# SLOT constraints.policy_A_trigger_excludes_B
model.addConstr(x[0] + x[1] <= 1, name="policy_A_trigger_excludes_B")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)
    if not math.isfinite(objective):
        objective = None

    constraint_violations = [
        abs(sum(values) - 3.0),
        max(0.0, 1.0 - (values[0] + values[1] + values[3])),
        max(0.0, 1.0 - (values[1] + values[2] + values[4])),
        max(0.0, values[4] + values[5] - 1.0),
        max(0.0, values[0] + values[1] - 1.0),
    ]
    max_constraint_violation = max(constraint_violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    objective = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

# For this instance the optimal output is objective 2769 and action [1,0,1,1,0,0].
result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False))
