import gurobipy
import json
import math

model = gurobipy.Model("SWOR031_patched")
model.Params.OutputFlag = 0

# VARIABLES
semantic_names = [
    "服务模块A", "服务模块B", "服务模块C", "服务模块D",
    "服务模块E", "服务模块F", "服务模块G"
]
x = [
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}")
    for i in range(7)
]
model.update()

# OBJECTIVE
profits = [1015, 954, 912, 851, 790, 748, 687]
model.setObjective(
    gurobipy.quicksum(profits[i] * x[i] for i in range(7)),
    gurobipy.GRB.MAXIMIZE
)

# C_BASE_01_MAX_MODULES
model.addConstr(gurobipy.quicksum(x) <= 3, name="c_max_modules")

# C_BASE_02_ZONE_1
model.addConstr(x[0] + x[3] + x[6] >= 1, name="c_zone_1")

# C_BASE_03_ZONE_2
model.addConstr(x[1] + x[4] >= 1, name="c_zone_2")

# C_BASE_04_ZONE_3
model.addConstr(x[2] + x[5] >= 1, name="c_zone_3")

# C_BASE_05_A_REQUIRES_BACKHAUL
model.addConstr(x[0] - x[1] - x[4] <= 0, name="c_A_requires_B_or_E")

# C_BASE_06_CORE_CANDIDATES
model.addConstr(x[0] + x[1] + x[2] >= 2, name="c_core_at_least_two")

# C_PATCH_01_DOC_82B25BAC834CA2C8
model.addConstr(x[0] == 0, name="c_policy_A_ineligible")

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
    raw = [var.X for var in x]
    projected_action = [int(round(value)) for value in raw]
    violations = [
        max(0.0, sum(raw) - 3.0),
        max(0.0, 1.0 - (raw[0] + raw[3] + raw[6])),
        max(0.0, 1.0 - (raw[1] + raw[4])),
        max(0.0, 1.0 - (raw[2] + raw[5])),
        max(0.0, raw[0] - raw[1] - raw[4]),
        max(0.0, 2.0 - (raw[0] + raw[1] + raw[2])),
        abs(raw[0])
    ]
    integrality_violation = max(
        min(abs(value), abs(1.0 - value)) for value in raw
    )
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "selected_modules": [
            semantic_names[i] for i, value in enumerate(projected_action) if value == 1
        ],
        "max_constraint_violation": max(violations),
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0, 0, 0, 0, 0, 0, 0],
        "selected_modules": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))
