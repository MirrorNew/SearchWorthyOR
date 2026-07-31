import gurobipy as gp
import json
import math

model = gp.Model("SWOR046")
model.Params.OutputFlag = 0

x = [
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_0"),
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_1"),
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_2"),
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_3"),
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_4"),
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_5"),
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_6")
]

returns = [1007, 965, 904, 843, 801, 740, 698]
capital = [3, 4, 1, 2, 3, 4, 1]
risk = [3, 5, 2, 4, 1, 3, 5]

model.setObjective(gp.quicksum(returns[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x[i] for i in range(7)) == 3, name="position_count")
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(7)) <= 12, name="capital_limit")
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(7)) <= 15, name="risk_limit")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_minimum")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(int(model.Status)))

if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in values]
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, sum(capital[i] * values[i] for i in range(7)) - 12.0),
        max(0.0, sum(risk[i] * values[i] for i in range(7)) - 15.0),
        max(0.0, 2.0 - sum(values[i] for i in range(3)))
    ]
    bound_violations = [max(0.0, -v, v - 1.0) for v in values]
    integrality_violation = max(abs(v - round(v)) for v in values)
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": max(violations + bound_violations),
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": None,
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))
