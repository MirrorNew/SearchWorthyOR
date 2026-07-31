import gurobipy as gp
import json

# REGION_VARIABLES
model = gp.Model("SWOR031_patched")
model.Params.OutputFlag = 0
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

# REGION_OBJECTIVE
revenues = [1015, 954, 912, 851, 790, 748, 687]
model.setObjective(gp.quicksum(revenues[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# REGION_BASE_CARDINALITY
model.addConstr(gp.quicksum(x) <= 3, name="base_module_limit")

# REGION_BASE_ZONE1
model.addConstr(x[0] + x[3] + x[6] >= 1, name="base_zone1_connectivity")

# REGION_BASE_ZONE2
model.addConstr(x[1] + x[4] >= 1, name="base_zone2_connectivity")

# REGION_BASE_ZONE3
model.addConstr(x[2] + x[5] >= 1, name="base_zone3_connectivity")

# REGION_BASE_BACKHAUL
model.addConstr(x[0] - x[1] - x[4] <= 0, name="base_a_backhaul_link")

# REGION_BASE_CORE
model.addConstr(x[0] + x[1] + x[2] >= 2, name="base_core_minimum")

# REGION_POLICY_PATCH
model.addConstr(x[0] == 0, name="policy_module_a_ineligible")

# REGION_SOLVE_OUTPUT
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
    "projected_action": None,
    "max_constraint_violation": None,
    "integrality_violation": None
}
if model.SolCount > 0:
    values = [v.X for v in x]
    projected = [int(round(value)) for value in values]
    checks = [
        (sum(values), "<=", 3),
        (values[0] + values[3] + values[6], ">=", 1),
        (values[1] + values[4], ">=", 1),
        (values[2] + values[5], ">=", 1),
        (values[0] - values[1] - values[4], "<=", 0),
        (values[0] + values[1] + values[2], ">=", 2),
        (values[0], "==", 0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    result["objective"] = model.ObjVal
    result["projected_action"] = projected
    result["max_constraint_violation"] = max(violations)
    result["integrality_violation"] = max(abs(value - round(value)) for value in values)
print(json.dumps(result, ensure_ascii=False))
