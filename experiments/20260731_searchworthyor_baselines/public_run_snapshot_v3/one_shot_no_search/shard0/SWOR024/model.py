import gurobipy as gp
import json

model = gp.Model("SWOR024")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
model.update()

benefits = [1013, 952, 910, 849, 788, 746, 685]
capacity_use = [3, 4, 1, 2, 3, 4, 1]

model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x[i] for i in range(7)) <= 3, name="maximum_enabled_modes")
model.addConstr(gp.quicksum(capacity_use[i] * x[i] for i in range(7)) <= 8, name="equipment_capacity")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_modes_minimum")

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
    values = [float(x[i].X) for i in range(7)]
    projected_action = [int(round(value)) for value in values]
    violations = [
        max(0.0, sum(values) - 3.0),
        max(0.0, sum(capacity_use[i] * values[i] for i in range(7)) - 8.0),
        max(0.0, 2.0 - sum(values[i] for i in range(3)))
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal)
else:
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
