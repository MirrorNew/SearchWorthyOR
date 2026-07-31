import gurobipy as gp
import json
import math

model = gp.Model("SWOR008_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
values = [1016, 955, 894, 852, 791, 749, 688]
resources = [4, 1, 2, 3, 4, 1, 2]
x = model.addVars(names, vtype=gp.GRB.BINARY, lb=0, ub=1, name="enable")

# OBJECTIVE
model.setObjective(
    gp.quicksum(values[j] * x[names[j]] for j in range(len(names))),
    gp.GRB.MAXIMIZE,
)

# BASE_CONSTRAINTS
model.addConstr(gp.quicksum(x[n] for n in names) == 3, name="build_exactly_three")
model.addConstr(x["x_0"] + x["x_2"] + x["x_4"] + x["x_6"] >= 1, name="cover_service_area_1")
model.addConstr(x["x_1"] + x["x_3"] + x["x_5"] >= 1, name="cover_service_area_2")
model.addConstr(x["x_1"] + x["x_4"] + x["x_6"] == 1, name="choose_exactly_one_B_E_G")

# EVIDENCE_PATCH_DISPOSAL: DOC-A2E3D710FE9DBFE9
model.addConstr(x["x_0"] + x["x_1"] <= 1, name="replacement_asset_disposal_conflict")

model.optimize()

status = "OPTIMAL" if model.Status == gp.GRB.OPTIMAL else str(model.Status)
if model.SolCount > 0:
    raw = [float(x[n].X) for n in names]
    projected = [int(v >= 0.5) for v in raw]
    objective = float(model.ObjVal)
    integrality_violation = max(abs(v - round(v)) for v in raw)

    checks = [
        (sum(raw), "==", 3.0),
        (raw[0] + raw[2] + raw[4] + raw[6], ">=", 1.0),
        (raw[1] + raw[3] + raw[5], ">=", 1.0),
        (raw[1] + raw[4] + raw[6], "==", 1.0),
        (raw[0] + raw[1], "<=", 1.0),
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    max_constraint_violation = max(violations)
    resource_points_report_only = sum(resources[j] * projected[j] for j in range(len(names)))
else:
    objective = None
    projected = [0 for _ in names]
    max_constraint_violation = None
    integrality_violation = None
    resource_points_report_only = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
    "resource_points_report_only": resource_points_report_only,
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
