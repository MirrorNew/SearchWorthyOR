import gurobipy as gp
import json

model = gp.Model("SWOR017_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
benefits = [1005, 963, 902, 841, 799, 738, 696, 635]
capacity = [3, 4, 1, 2, 3, 4, 1, 2]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]

model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) <= 3, name="max_three_modes")
model.addConstr(gp.quicksum(capacity[i] * x[i] for i in range(8)) <= 8, name="equipment_capacity")
model.addConstr(x[6] + x[7] <= 1, name="terminal_backup_mutex")
model.addConstr(x[0] + x[1] <= 1, name="external_A_excludes_B")

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
    values = [v.X for v in x]
    projected_action = [int(value >= 0.5) for value in values]
    lhs_values = [
        sum(values),
        sum(capacity[i] * values[i] for i in range(8)),
        values[6] + values[7],
        values[0] + values[1]
    ]
    rhs_values = [3.0, 8.0, 1.0, 1.0]
    max_constraint_violation = max([0.0] + [max(0.0, lhs_values[i] - rhs_values[i]) for i in range(4)])
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
else:
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None
    objective = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))
