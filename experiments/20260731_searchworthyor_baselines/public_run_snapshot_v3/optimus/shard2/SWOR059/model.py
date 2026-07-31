import gurobipy
import json
import math

# REGION_DATA
revenues = [1000, 958, 897, 855, 794, 752]
resource_points = [1, 2, 3, 4, 1, 2]
categories = ["基础类别", "基础类别", "基础类别", "基础类别", "保障类别1", "保障类别2"]

model = gurobipy.Model("SWOR059_patched")
model.Params.OutputFlag = 0

# REGION_VARIABLES
x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

# REGION_OBJECTIVE
model.setObjective(gurobipy.quicksum(revenues[i] * x[i] for i in range(6)), gurobipy.GRB.MAXIMIZE)

# REGION_BASE_SEGMENT_1
model.addConstr(x[0] + x[3] == 1, name="segment_1_exactly_one")

# REGION_BASE_SEGMENT_2
model.addConstr(x[1] + x[4] == 1, name="segment_2_exactly_one")

# REGION_BASE_SEGMENT_3
model.addConstr(x[2] + x[5] == 1, name="segment_3_exactly_one")

# REGION_POLICY_DOC_1AAB4541D0AFF6A2
model.addConstr(x[0] + x[1] <= 1, name="policy_A_implies_not_B")

# REGION_SOLVE
model.optimize()
status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

# REGION_OUTPUT
if model.SolCount > 0:
    raw = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in raw]
    violations = [
        abs(raw[0] + raw[3] - 1.0),
        abs(raw[1] + raw[4] - 1.0),
        abs(raw[2] + raw[5] - 1.0),
        max(0.0, raw[0] + raw[1] - 1.0)
    ]
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(v - round(v)) for v in raw)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }
print(json.dumps(result, ensure_ascii=False))