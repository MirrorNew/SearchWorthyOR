import gurobipy as gp
import json

model = gp.Model("SWOR016")
model.Params.OutputFlag = 0

x = [
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}")
    for i in range(8)
]

profits = [1007, 965, 904, 843, 801, 740, 698, 637]
model.setObjective(
    gp.quicksum(profits[i] * x[i] for i in range(8)),
    gp.GRB.MAXIMIZE
)

model.addConstr(gp.quicksum(x) == 3, name="build_exactly_3")
model.addConstr(x[0] + x[2] + x[4] + x[6] >= 1, name="cover_service_area_1")
model.addConstr(x[1] + x[3] + x[5] + x[7] >= 1, name="cover_service_area_2")
model.addConstr(x[1] + x[4] + x[7] == 1, name="exactly_one_B_E_H")

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
    values = [float(v.X) for v in x]
    projected_action = [int(round(value)) for value in values]
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, 1.0 - (values[0] + values[2] + values[4] + values[6])),
        max(0.0, 1.0 - (values[1] + values[3] + values[5] + values[7])),
        abs(values[1] + values[4] + values[7] - 1.0)
    ]
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(value - round(value)) for value in values)
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
