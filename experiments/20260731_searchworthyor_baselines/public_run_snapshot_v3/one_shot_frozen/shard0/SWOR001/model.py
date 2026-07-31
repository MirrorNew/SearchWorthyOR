import gurobipy as gp
import json
import math

# [REGION:MODEL_SETUP]
model = gp.Model("SWOR001_patched")
model.Params.OutputFlag = 0

# [REGION:VARIABLES]
semantic_names = ["模式A", "模式B", "模式C", "模式D", "模式E", "模式F"]
x = [
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}")
    for i in range(6)
]

# [REGION:OBJECTIVE]
profits = [1015, 954, 912, 851, 790, 748]
model.setObjective(
    gp.quicksum(profits[i] * x[i] for i in range(6)),
    gp.GRB.MAXIMIZE,
)

# [REGION:CONSTRAINT_MAX_MODES]
model.addConstr(gp.quicksum(x) <= 3, name="max_enabled_modes")

# [REGION:CONSTRAINT_CAPACITY]
capacity_use = [4, 1, 2, 3, 4, 1]
model.addConstr(
    gp.quicksum(capacity_use[i] * x[i] for i in range(6)) <= 7,
    name="equipment_capacity",
)

# [REGION:CONSTRAINT_EF]
model.addConstr(x[4] + x[5] <= 1, name="backup_modes_E_F_incompatible")

# [REGION:CONSTRAINT_POLICY_AB]
model.addConstr(x[0] + x[1] <= 1, name="policy_A_branch_excludes_B")

# [REGION:SOLVE]
model.optimize()

# [REGION:OUTPUT]
if model.Status == gp.GRB.OPTIMAL:
    status = "OPTIMAL"
elif model.Status == gp.GRB.INFEASIBLE:
    status = "INFEASIBLE"
elif model.Status == gp.GRB.UNBOUNDED:
    status = "UNBOUNDED"
elif model.Status == gp.GRB.INF_OR_UNBD:
    status = "INF_OR_UNBD"
else:
    status = str(model.Status)

if model.SolCount > 0:
    raw_action = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in raw_action]
    violations = [
        max(0.0, sum(raw_action) - 3.0),
        max(0.0, sum(capacity_use[i] * raw_action[i] for i in range(6)) - 7.0),
        max(0.0, raw_action[4] + raw_action[5] - 1.0),
        max(0.0, raw_action[0] + raw_action[1] - 1.0),
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(
        abs(value - round(value)) for value in raw_action
    )
    objective = float(model.ObjVal)
else:
    objective = None
    projected_action = []
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