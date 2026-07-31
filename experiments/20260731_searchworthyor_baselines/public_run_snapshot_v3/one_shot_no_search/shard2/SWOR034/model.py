import gurobipy as gp
import json
import math

model = gp.Model("SWOR034")
model.Params.OutputFlag = 0

# VARIABLES
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
model.update()

# OBJ
utility = [1000, 958, 897, 855, 794, 752, 691, 630]
model.setObjective(gp.quicksum(utility[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

# C_MODULE_LIMIT
model.addConstr(gp.quicksum(x[i] for i in range(8)) <= 3, name="module_limit")

# C_ZONE_1
model.addConstr(x[0] + x[3] + x[6] >= 1, name="zone_1_connectivity")

# C_ZONE_2
model.addConstr(x[1] + x[4] + x[7] >= 1, name="zone_2_connectivity")

# C_ZONE_3
model.addConstr(x[2] + x[5] >= 1, name="zone_3_connectivity")

# C_A_BACKHAUL
model.addConstr(-x[0] + x[1] + x[4] >= 0, name="module_A_backhaul")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw = [x[i].X for i in range(8)]
    projected_action = [int(round(value)) for value in raw]
    lhs_values = [
        sum(raw),
        raw[0] + raw[3] + raw[6],
        raw[1] + raw[4] + raw[7],
        raw[2] + raw[5],
        -raw[0] + raw[1] + raw[4]
    ]
    violations = [
        max(0.0, lhs_values[0] - 3.0),
        max(0.0, 1.0 - lhs_values[1]),
        max(0.0, 1.0 - lhs_values[2]),
        max(0.0, 1.0 - lhs_values[3]),
        max(0.0, 0.0 - lhs_values[4])
    ]
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(value - round(value)) for value in raw)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0, 0, 0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))
