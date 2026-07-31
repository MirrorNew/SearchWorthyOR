import gurobipy as gp
import json
import math

model = gp.Model("SWOR031_patched")
model.Params.OutputFlag = 0

# C_VARIABLE_DOMAIN
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

# C_OBJECTIVE
benefit = [1015, 954, 912, 851, 790, 748, 687]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# C_BASE_CAP
model.addConstr(gp.quicksum(x) <= 3, name="maximum_enabled_modules")
# C_BASE_ZONE_1
model.addConstr(x[0] + x[3] + x[6] >= 1, name="zone_1_coverage")
# C_BASE_ZONE_2
model.addConstr(x[1] + x[4] >= 1, name="zone_2_coverage")
# C_BASE_ZONE_3
model.addConstr(x[2] + x[5] >= 1, name="zone_3_coverage")
# C_BASE_BACKHAUL
model.addConstr(x[0] - x[1] - x[4] <= 0, name="module_A_backhaul_requirement")
# C_BASE_CORE
model.addConstr(x[0] + x[1] + x[2] >= 2, name="minimum_core_modules")
# C_POLICY_A_INELIGIBLE: DOC-82B25BAC834CA2C8
model.addConstr(x[0] == 0, name="policy_module_A_ineligible")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": None,
    "projected_action": [],
    "max_constraint_violation": None,
    "integrality_violation": None
}

if model.SolCount > 0:
    values = [x[i].X for i in range(7)]
    projected = [int(round(v)) for v in values]
    violations = [
        max(0.0, sum(values) - 3.0),
        max(0.0, 1.0 - (values[0] + values[3] + values[6])),
        max(0.0, 1.0 - (values[1] + values[4])),
        max(0.0, 1.0 - (values[2] + values[5])),
        max(0.0, values[0] - values[1] - values[4]),
        max(0.0, 2.0 - (values[0] + values[1] + values[2])),
        abs(values[0])
    ]
    result["objective"] = model.ObjVal
    result["projected_action"] = projected
    result["max_constraint_violation"] = max(violations)
    result["integrality_violation"] = max(abs(v - round(v)) for v in values)

print(json.dumps(result, ensure_ascii=False, allow_nan=False))