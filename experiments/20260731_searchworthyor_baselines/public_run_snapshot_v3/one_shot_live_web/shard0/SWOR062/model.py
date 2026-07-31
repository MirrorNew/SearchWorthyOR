import gurobipy
import json
import math

model = gurobipy.Model("SWOR062")
model.Params.OutputFlag = 0

# VARIABLES AND OBJECTIVE
x = [
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}")
    for i in range(8)
]
benefits = [1016, 955, 894, 852, 791, 749, 688, 646]
resources = [1, 2, 3, 4, 1, 2, 3, 4]
model.setObjective(
    gurobipy.quicksum(benefits[i] * x[i] for i in range(8)),
    gurobipy.GRB.MAXIMIZE,
)

# BASE CONSTRAINTS
model.addConstr(gurobipy.quicksum(x) <= 3, name="max_energy_units")
model.addConstr(
    gurobipy.quicksum(resources[i] * x[i] for i in range(8)) <= 6,
    name="grid_resource_capacity",
)
model.addConstr(x[0] + x[3] + x[6] >= 1, name="clean_capability_required")
model.addConstr(x[1] + x[4] + x[7] >= 1, name="backup_capability_required")
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_D_required")

# POLICY PATCH: 150 kg/month non-acute waste cannot use the ordinary VSQG path
model.addConstr(x[0] <= 0, name="policy_no_vsqg_path_at_150kg")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
}
result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": None,
    "projected_action": [],
    "max_constraint_violation": None,
    "integrality_violation": None,
}

# SOLUTION AND VALIDATION
if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected = [int(round(value)) for value in values]
    violations = [
        max(0.0, sum(values) - 3.0),
        max(0.0, sum(resources[i] * values[i] for i in range(8)) - 6.0),
        max(0.0, 1.0 - (values[0] + values[3] + values[6])),
        max(0.0, 1.0 - (values[1] + values[4] + values[7])),
        max(0.0, 1.0 - (values[0] + values[3])),
        max(0.0, values[0]),
    ]
    integrality = max(abs(value - round(value)) for value in values)
    result.update({
        "objective": float(model.ObjVal),
        "projected_action": projected,
        "max_constraint_violation": float(max(violations)),
        "integrality_violation": float(integrality),
    })

print(json.dumps(result, ensure_ascii=False, allow_nan=False))