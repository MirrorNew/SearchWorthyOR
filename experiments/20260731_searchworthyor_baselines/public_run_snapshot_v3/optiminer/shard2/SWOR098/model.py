import gurobipy
import json

model = gurobipy.Model("SWOR098")
model.Params.OutputFlag = 0

x = [
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name="x_%d" % i)
    for i in range(8)
]

profits = [1009, 948, 906, 845, 803, 742, 700, 639]
model.setObjective(
    gurobipy.quicksum(profits[i] * x[i] for i in range(8)),
    gurobipy.GRB.MAXIMIZE,
)

model.addConstr(gurobipy.quicksum(x) <= 3, name="unit_count_limit")
model.addConstr(3*x[0] + 4*x[1] + x[2] + 2*x[3] + 3*x[4] + 4*x[5] + x[6] + 2*x[7] <= 8, name="grid_resource_limit")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="clean_capability_minimum")
model.addConstr(x[1] + x[4] + x[7] >= 1, name="backup_capability_minimum")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_candidate_minimum")
model.addConstr(x[0] + x[1] <= 1, name="policy_mutual_exclusion_A_B")

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
    values = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in values]
    lhs_values = [
        sum(values),
        3*values[0] + 4*values[1] + values[2] + 2*values[3] + 3*values[4] + 4*values[5] + values[6] + 2*values[7],
        values[0] + values[3] + values[6],
        values[1] + values[4] + values[7],
        values[0] + values[1] + values[2],
        values[0] + values[1],
    ]
    senses = ["<=", "<=", ">=", ">=", ">=", "<="]
    rhs_values = [3.0, 8.0, 1.0, 1.0, 2.0, 1.0]
    violations = []
    for lhs, sense, rhs in zip(lhs_values, senses, rhs_values):
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    output = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(v - round(v)) for v in values),
    }
else:
    output = {
        "status": status,
        "objective": None,
        "projected_action": None,
        "max_constraint_violation": None,
        "integrality_violation": None,
    }

print(json.dumps(output, ensure_ascii=False, allow_nan=False))