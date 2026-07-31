import gurobipy as gp
import json
import math

model = gp.Model("SWOR030_patched")
model.Params.OutputFlag = 0

# REGION: variables
semantic_names = ["模式A", "模式B", "模式C", "模式D", "模式E", "模式F"]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
model.update()

# REGION: objective_public_task
values = [1003, 961, 900, 858, 797, 736]
model.setObjective(gp.quicksum(values[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

# REGION: constraints_public_task
model.addConstr(gp.quicksum(x) <= 3, name="max_enabled_modes")
capacities = [2, 3, 4, 1, 2, 3]
model.addConstr(gp.quicksum(capacities[i] * x[i] for i in range(6)) <= 9, name="equipment_capacity")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="minimum_core_modes")

# REGION: constraint_DOC_DE855EAAC40618F5
model.addConstr(x[0] + x[1] <= 1, name="policy_AB_mutual_exclusion")

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
    "projected_action": [0, 0, 0, 0, 0, 0],
    "max_constraint_violation": None,
    "integrality_violation": None
}

if model.SolCount > 0:
    values_raw = [var.X for var in x]
    projected = [int(round(value)) for value in values_raw]
    constraint_rows = [
        (sum(values_raw), "<=", 3),
        (sum(capacities[i] * values_raw[i] for i in range(6)), "<=", 9),
        (values_raw[0] + values_raw[1] + values_raw[2], ">=", 2),
        (values_raw[0] + values_raw[1], "<=", 1)
    ]
    violations = []
    for lhs, sense, rhs in constraint_rows:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    integrality_violation = max(abs(value - round(value)) for value in values_raw)
    objective = model.ObjVal
    result = {
        "status": status_names.get(model.Status, str(model.Status)),
        "objective": objective if math.isfinite(objective) else None,
        "projected_action": projected,
        "max_constraint_violation": max(violations),
        "integrality_violation": integrality_violation
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))
