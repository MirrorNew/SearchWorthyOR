import gurobipy as gp
import json
import math

model = gp.Model("SWOR089")
model.Params.OutputFlag = 0

semantic_names = [
    "选择补货包A",
    "选择补货包B",
    "选择补货包C",
    "选择补货包D",
    "选择补货包E",
    "选择补货包F",
    "选择补货包G"
]
profits = [1004, 962, 901, 859, 798, 737, 695]

x = [
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}")
    for i in range(7)
]
model.update()

model.setObjective(
    gp.quicksum(profits[i] * x[i] for i in range(7)),
    gp.GRB.MAXIMIZE
)

model.addConstr(gp.quicksum(x[i] for i in range(7)) == 3, name="select_exactly_three")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="front_stage_supply")
model.addConstr(x[1] + x[2] + x[4] >= 1, name="back_stage_supply")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(value >= 0.5) for value in values]
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, 1.0 - (values[0] + values[1] + values[3] + values[6])),
        max(0.0, 1.0 - (values[1] + values[2] + values[4]))
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
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