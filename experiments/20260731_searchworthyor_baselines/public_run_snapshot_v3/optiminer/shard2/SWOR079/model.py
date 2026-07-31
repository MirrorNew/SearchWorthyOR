import gurobipy
import json

model = gurobipy.Model("SWOR079_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0
model.Params.FeasibilityTol = 1e-9
model.Params.IntFeasTol = 1e-9

x = [
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}")
    for i in range(6)
]

objective_coefficients = [1010, 949, 907, 846, 804, 743]
model.setObjective(
    gurobipy.quicksum(objective_coefficients[i] * x[i] for i in range(6)),
    gurobipy.GRB.MAXIMIZE,
)

model.addConstr(gurobipy.quicksum(x) <= 3, name="module_count_limit")
model.addConstr(x[0] + x[3] >= 1, name="zone_1_connectivity")
model.addConstr(x[1] + x[4] >= 1, name="zone_2_connectivity")
model.addConstr(x[2] + x[5] >= 1, name="zone_3_connectivity")
model.addConstr(x[0] - x[1] - x[4] <= 0, name="access_backhaul_requirement")
model.addConstr(x[4] + x[5] >= 1, name="policy_safeguard_option")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected_action = [int(value >= 0.5) for value in values]
    checks = [
        (sum(values), "<=", 3.0),
        (values[0] + values[3], ">=", 1.0),
        (values[1] + values[4], ">=", 1.0),
        (values[2] + values[5], ">=", 1.0),
        (values[0] - values[1] - values[4], "<=", 0.0),
        (values[4] + values[5], ">=", 1.0),
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(value - round(value)) for value in values),
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None,
    }

print(json.dumps(result, ensure_ascii=False, sort_keys=True))
