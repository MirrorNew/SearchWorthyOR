import gurobipy as gp
import json
import math

# [MODEL_DATA]
names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
utilities = [1010, 949, 907, 846, 804, 743, 682, 640]
clinical_resource_points = [2, 3, 4, 1, 2, 3, 4, 1]
business_attributes = ["基础类别", "基础类别", "基础类别", "基础类别", "基础类别", "基础类别", "保障类别1", "保障类别2"]

model = gp.Model("SWOR076")
model.Params.OutputFlag = 0

# [VARIABLES]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]

# [OBJECTIVE]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

# [C_COUNT]
model.addConstr(gp.quicksum(x) == 3, name="exactly_three_blocks")

# [C_EMERGENCY]
model.addConstr(x[0] + x[1] >= 1, name="emergency_coverage")

# [C_CONTINUITY]
model.addConstr(x[1] + x[2] >= 1, name="continuity_coverage")

# [C_SPECIALTY]
model.addConstr(x[0] + x[2] >= 1, name="specialty_coverage")

# [C_BACKUP_MUTEX]
model.addConstr(x[6] + x[7] <= 1, name="backup_mutex")

# [SOLVE_AND_REPORT]
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
    values = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in values]
    lhs_values = [
        sum(values),
        values[0] + values[1],
        values[1] + values[2],
        values[0] + values[2],
        values[6] + values[7]
    ]
    violations = [
        abs(lhs_values[0] - 3.0),
        max(0.0, 1.0 - lhs_values[1]),
        max(0.0, 1.0 - lhs_values[2]),
        max(0.0, 1.0 - lhs_values[3]),
        max(0.0, lhs_values[4] - 1.0)
    ]
    integrality_violation = max(abs(v - round(v)) for v in values)
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": float(max(violations)),
        "integrality_violation": float(integrality_violation)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0, 0, 0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))
