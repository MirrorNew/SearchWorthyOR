import gurobipy as gp
import json

model = gp.Model("SWOR043_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

model.setObjective(
    1010 * x[0] + 949 * x[1] + 907 * x[2]
    + 846 * x[3] + 804 * x[4] + 743 * x[5],
    gp.GRB.MAXIMIZE,
)

model.addConstr(gp.quicksum(x) == 3, name="exactly_three_assignments")
model.addConstr(x[0] + x[3] <= 1, name="subject1_at_most_one")
model.addConstr(x[1] + x[4] <= 1, name="subject2_at_most_one")
model.addConstr(x[2] + x[5] <= 1, name="subject3_at_most_one")
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_D_at_least_one")
model.addConstr(x[0] + x[1] <= 1, name="policy_A_excludes_B")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    violations = [
        abs(sum(values) - 3),
        max(0.0, values[0] + values[3] - 1),
        max(0.0, values[1] + values[4] - 1),
        max(0.0, values[2] + values[5] - 1),
        max(0.0, 1 - values[0] - values[3]),
        max(0.0, values[0] + values[1] - 1),
    ]
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": float(max(violations)),
        "integrality_violation": float(max(abs(value - round(value)) for value in values)),
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": None,
        "max_constraint_violation": None,
        "integrality_violation": None,
    }

print(json.dumps(result, ensure_ascii=False))
