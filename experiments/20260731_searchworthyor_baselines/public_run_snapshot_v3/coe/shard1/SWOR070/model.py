import gurobipy as gp
import json
import math

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
profit = [1001, 959, 898, 856, 795, 753]
resource = [3, 4, 1, 2, 3, 4]

model = gp.Model("SWOR070_patched")
model.Params.OutputFlag = 0
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=n) for n in names]

model.setObjective(gp.quicksum(profit[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) <= 3, name="B1_max_units")
model.addConstr(gp.quicksum(resource[i] * x[i] for i in range(6)) <= 8, name="B2_grid_resources")
model.addConstr(x[0] + x[3] >= 1, name="B3_clean_capability")
model.addConstr(x[1] + x[4] >= 1, name="B4_reserve_capability")
model.addConstr(x[4] + x[5] <= 1, name="B5_E_F_mutex")
model.addConstr(x[4] + x[5] >= 1, name="P1_safeguard_option")

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
    values = [v.X for v in x]
    projected = [int(round(v)) for v in values]
    lhs_values = [
        sum(values),
        sum(resource[i] * values[i] for i in range(6)),
        values[0] + values[3],
        values[1] + values[4],
        values[4] + values[5],
        values[4] + values[5]
    ]
    senses = ["<=", "<=", ">=", ">=", "<=", ">="]
    rhs_values = [3, 8, 1, 1, 1, 1]
    violations = []
    for lhs, sense, rhs in zip(lhs_values, senses, rhs_values):
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))
    integrality_violation = max(abs(value - round(value)) for value in values)
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected,
        "max_constraint_violation": max(violations),
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))
