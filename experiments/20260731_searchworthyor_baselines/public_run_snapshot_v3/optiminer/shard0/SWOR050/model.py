import gurobipy as gp
import json
import math

model = gp.Model("SWOR050_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
model.setObjective(
    1007 * x[0] + 965 * x[1] + 904 * x[2] +
    843 * x[3] + 801 * x[4] + 740 * x[5],
    gp.GRB.MAXIMIZE
)

model.addConstr(gp.quicksum(x) <= 3, name="max_enabled_units")
model.addConstr(2*x[0] + 3*x[1] + 4*x[2] + x[3] + 2*x[4] + 3*x[5] <= 9, name="grid_resource_capacity")
model.addConstr(x[0] + x[3] >= 1, name="minimum_clean_capability")
model.addConstr(x[1] + x[4] >= 1, name="minimum_backup_capability")
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_backup_D")
# POLICY_PATCH DOC-9E7B5FF9625AA0CB: A不具备采用资格
model.addConstr(x[0] == 0, name="policy_A_ineligible")

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
    raw = [float(v.X) for v in x]
    projected_action = [int(round(value)) for value in raw]
    integrality_violation = max(abs(value - round(value)) for value in raw)

    lhs_values = [
        sum(raw),
        2*raw[0] + 3*raw[1] + 4*raw[2] + raw[3] + 2*raw[4] + 3*raw[5],
        raw[0] + raw[3],
        raw[1] + raw[4],
        raw[0] + raw[3],
        raw[0]
    ]
    violations = [
        max(0.0, lhs_values[0] - 3.0),
        max(0.0, lhs_values[1] - 9.0),
        max(0.0, 1.0 - lhs_values[2]),
        max(0.0, 1.0 - lhs_values[3]),
        max(0.0, 1.0 - lhs_values[4]),
        abs(lhs_values[5])
    ]
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
        "projected_action": [0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))