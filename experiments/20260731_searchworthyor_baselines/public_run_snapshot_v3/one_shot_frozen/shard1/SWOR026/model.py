import gurobipy as gp
import json
import math

model = gp.Model("SWOR026_patched")
model.Params.OutputFlag = 0

variable_specs = [
    ("x_0", "服务模块A"),
    ("x_1", "服务模块B"),
    ("x_2", "服务模块C"),
    ("x_3", "服务模块D"),
    ("x_4", "服务模块E"),
    ("x_5", "服务模块F"),
    ("x_6", "服务模块G"),
]
x = {
    name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name)
    for name, semantic_name in variable_specs
}
model.update()

objective_terms = {
    "x_0": 1002,
    "x_1": 960,
    "x_2": 899,
    "x_3": 857,
    "x_4": 796,
    "x_5": 735,
    "x_6": 693,
}
model.setObjective(
    gp.quicksum(coefficient * x[name] for name, coefficient in objective_terms.items()),
    gp.GRB.MAXIMIZE,
)

constraints_data = [
    ("c_max_modules", "<=", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1}),
    ("c_zone_1", ">=", 1, {"x_0": 1, "x_3": 1, "x_6": 1}),
    ("c_zone_2", ">=", 1, {"x_1": 1, "x_4": 1}),
    ("c_zone_3", ">=", 1, {"x_2": 1, "x_5": 1}),
    ("c_A_requires_B_or_E", "<=", 0, {"x_0": 1, "x_1": -1, "x_4": -1}),
    ("c_exactly_one_B_E_G", "==", 1, {"x_1": 1, "x_4": 1, "x_6": 1}),
    ("c_policy_A_excludes_B", "<=", 1, {"x_0": 1, "x_1": 1}),
]

for name, sense, rhs, terms in constraints_data:
    expression = gp.quicksum(coefficient * x[var_name] for var_name, coefficient in terms.items())
    if sense == "<=":
        model.addConstr(expression <= rhs, name=name)
    elif sense == ">=":
        model.addConstr(expression >= rhs, name=name)
    else:
        model.addConstr(expression == rhs, name=name)

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
}
status = status_names.get(model.Status, "STATUS_" + str(model.Status))
projection = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]

if model.SolCount > 0:
    values = {name: float(x[name].X) for name in projection}
    projected_action = [int(values[name] >= 0.5) for name in projection]
    objective = float(model.ObjVal)
    max_constraint_violation = 0.0
    for name, sense, rhs, terms in constraints_data:
        lhs = sum(coefficient * values[var_name] for var_name, coefficient in terms.items())
        if sense == "<=":
            violation = max(0.0, lhs - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs)
        else:
            violation = abs(lhs - rhs)
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(abs(values[name] - round(values[name])) for name in projection)
else:
    objective = None
    projected_action = [0 for name in projection]
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
