import gurobipy
import json

model = gurobipy.Model("SWOR085")
model.Params.OutputFlag = 0

x = [
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0.0, ub=1.0, name="x_0"),
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0.0, ub=1.0, name="x_1"),
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0.0, ub=1.0, name="x_2"),
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0.0, ub=1.0, name="x_3"),
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0.0, ub=1.0, name="x_4"),
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0.0, ub=1.0, name="x_5"),
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0.0, ub=1.0, name="x_6"),
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0.0, ub=1.0, name="x_7")
]

values = [1018.0, 957.0, 896.0, 854.0, 793.0, 751.0, 690.0, 629.0]
capacity = [4.0, 1.0, 2.0, 3.0, 4.0, 1.0, 2.0, 3.0]

model.setObjective(gurobipy.quicksum(values[i] * x[i] for i in range(8)), gurobipy.GRB.MAXIMIZE)
model.addConstr(gurobipy.quicksum(x[i] for i in range(8)) <= 3.0, name="max_three_modes")
model.addConstr(gurobipy.quicksum(capacity[i] * x[i] for i in range(8)) <= 7.0, name="equipment_capacity")
model.addConstr(x[1] + x[4] + x[7] == 1.0, name="exactly_one_of_B_E_H")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
    gurobipy.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, "STATUS_" + str(model.Status))

if model.SolCount > 0:
    raw = [v.X for v in x]
    projected = [int(round(v)) for v in raw]
    violations = [
        max(0.0, sum(raw) - 3.0),
        max(0.0, sum(capacity[i] * raw[i] for i in range(8)) - 7.0),
        abs(raw[1] + raw[4] + raw[7] - 1.0)
    ]
    for value in raw:
        violations.append(max(0.0, -value, value - 1.0))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in raw)
    objective = model.ObjVal
else:
    projected = [0, 0, 0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None
    objective = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False, sort_keys=True))
