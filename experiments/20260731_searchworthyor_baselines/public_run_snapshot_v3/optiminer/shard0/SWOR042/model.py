import gurobipy
import json
import math

model = gurobipy.Model("SWOR042_patched")
model.Params.OutputFlag = 0

semantic_names = ["班次A", "班次B", "班次C", "班次D", "班次E", "班次F"]
x = {
    f"x_{i}": model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}")
    for i in range(6)
}
model.update()

objective_coefficients = {
    "x_0": 1002,
    "x_1": 960,
    "x_2": 899,
    "x_3": 857,
    "x_4": 796,
    "x_5": 735,
}
model.setObjective(
    gurobipy.quicksum(objective_coefficients[name] * x[name] for name in objective_coefficients),
    gurobipy.GRB.MAXIMIZE,
)

model.addConstr(gurobipy.quicksum(x[f"x_{i}"] for i in range(6)) == 3, name="base_exactly_three_blocks")
model.addConstr(x["x_0"] + x["x_3"] >= 1, name="base_period1_A_or_D")
model.addConstr(x["x_1"] + x["x_4"] >= 1, name="base_period2_B_or_E")
model.addConstr(x["x_2"] + x["x_5"] >= 1, name="base_period3_C_or_F")
model.addConstr(x["x_0"] + x["x_3"] >= 1, name="base_core_A_or_backup_D")
model.addConstr(x["x_0"] == 0, name="policy_A_unavailable")
model.addConstr(x["x_1"] == 0, name="policy_B_unavailable")

constraint_data = [
    ("==", 3.0, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}),
    (">=", 1.0, {"x_0": 1, "x_3": 1}),
    (">=", 1.0, {"x_1": 1, "x_4": 1}),
    (">=", 1.0, {"x_2": 1, "x_5": 1}),
    (">=", 1.0, {"x_0": 1, "x_3": 1}),
    ("==", 0.0, {"x_0": 1}),
    ("==", 0.0, {"x_1": 1}),
]
action_projection = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]

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
    values = {name: float(x[name].X) for name in action_projection}
    projected_action = [int(round(values[name])) for name in action_projection]
    integrality_violation = max(abs(value - round(value)) for value in values.values())
    violations = []
    for sense, rhs, terms in constraint_data:
        lhs = sum(coefficient * values[name] for name, coefficient in terms.items())
        if sense == "<=":
            violation = max(0.0, lhs - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs)
        else:
            violation = abs(lhs - rhs)
        violations.append(violation)
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": integrality_violation,
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None,
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))