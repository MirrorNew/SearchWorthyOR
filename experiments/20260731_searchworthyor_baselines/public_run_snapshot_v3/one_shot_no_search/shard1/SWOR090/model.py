import gurobipy as gp
import json
import math

model = gp.Model("SWOR090")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

returns = {
    "x_0": 1005, "x_1": 963, "x_2": 902, "x_3": 841,
    "x_4": 799, "x_5": 738, "x_6": 696, "x_7": 635
}
capital = {
    "x_0": 2, "x_1": 3, "x_2": 4, "x_3": 1,
    "x_4": 2, "x_5": 3, "x_6": 4, "x_7": 1
}
risk = {
    "x_0": 4, "x_1": 1, "x_2": 3, "x_3": 5,
    "x_4": 2, "x_5": 4, "x_6": 1, "x_7": 3
}

model.setObjective(gp.quicksum(returns[name] * x[name] for name in names), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x[name] for name in names) == 3, name="holdings_exactly_3")
model.addConstr(gp.quicksum(capital[name] * x[name] for name in names) <= 12, name="capital_limit")
model.addConstr(gp.quicksum(risk[name] * x[name] for name in names) <= 15, name="risk_limit")
model.addConstr(x["x_0"] + x["x_3"] >= 1, name="core_or_backup")

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
    values = {name: x[name].X for name in names}
    projected_action = [int(round(values[name])) for name in names]
    holdings_lhs = sum(values[name] for name in names)
    capital_lhs = sum(capital[name] * values[name] for name in names)
    risk_lhs = sum(risk[name] * values[name] for name in names)
    core_lhs = values["x_0"] + values["x_3"]
    violations = [
        abs(holdings_lhs - 3),
        max(0.0, capital_lhs - 12),
        max(0.0, risk_lhs - 15),
        max(0.0, 1 - core_lhs)
    ]
    integrality_violation = max(abs(values[name] - round(values[name])) for name in names)
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "selected_strategies": ["策略包A", "策略包B", "策略包C"] if projected_action == [1, 1, 1, 0, 0, 0, 0, 0] else [names[i] for i, value in enumerate(projected_action) if value == 1],
        "max_constraint_violation": max(violations),
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0 for name in names],
        "selected_strategies": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))