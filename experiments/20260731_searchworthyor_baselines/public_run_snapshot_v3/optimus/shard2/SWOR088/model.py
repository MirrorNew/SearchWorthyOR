import gurobipy as gp
import json
import math

model = gp.Model("SWOR088_patched")
model.Params.OutputFlag = 0

variable_data = [
    ("x_0", "选择路径包A"),
    ("x_1", "选择路径包B"),
    ("x_2", "选择路径包C"),
    ("x_3", "选择路径包D"),
    ("x_4", "选择路径包E"),
    ("x_5", "选择路径包F"),
    ("x_6", "选择路径包G"),
    ("x_7", "选择路径包H")
]
x = {
    name: model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=name)
    for name, semantic_name in variable_data
}

objective_terms = {
    "x_0": 1003.0,
    "x_1": 961.0,
    "x_2": 900.0,
    "x_3": 858.0,
    "x_4": 797.0,
    "x_5": 736.0,
    "x_6": 694.0,
    "x_7": 633.0
}
model.setObjective(
    gp.quicksum(coef * x[name] for name, coef in objective_terms.items()),
    gp.GRB.MAXIMIZE
)

constraints_data = [
    {"name": "leg_1_exactly_one", "sense": "==", "rhs": 1.0, "terms": {"x_0": 1.0, "x_3": 1.0, "x_6": 1.0}},
    {"name": "leg_2_exactly_one", "sense": "==", "rhs": 1.0, "terms": {"x_1": 1.0, "x_4": 1.0, "x_7": 1.0}},
    {"name": "leg_3_exactly_one", "sense": "==", "rhs": 1.0, "terms": {"x_2": 1.0, "x_5": 1.0}},
    {"name": "core_or_backup_minimum", "sense": ">=", "rhs": 1.0, "terms": {"x_0": 1.0, "x_3": 1.0}},
    {"name": "policy_route_A_11_hour_limit", "sense": "<=", "rhs": 0.0, "terms": {"x_0": 1.0}}
]

for constraint in constraints_data:
    lhs = gp.quicksum(
        coefficient * x[name]
        for name, coefficient in constraint["terms"].items()
    )
    if constraint["sense"] == "==":
        model.addConstr(lhs == constraint["rhs"], name=constraint["name"])
    elif constraint["sense"] == "<=":
        model.addConstr(lhs <= constraint["rhs"], name=constraint["name"])
    else:
        model.addConstr(lhs >= constraint["rhs"], name=constraint["name"])

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
    gp.GRB.NUMERIC: "NUMERIC",
    gp.GRB.SUBOPTIMAL: "SUBOPTIMAL"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: float(x[name].X) for name, semantic_name in variable_data}
    projected_action = [int(round(values[name])) for name, semantic_name in variable_data]
    raw_objective = float(model.ObjVal)
    objective = raw_objective if math.isfinite(raw_objective) else None
else:
    values = {name: 0.0 for name, semantic_name in variable_data}
    projected_action = [0 for name, semantic_name in variable_data]
    objective = None

violations = []
for constraint in constraints_data:
    lhs_value = sum(
        coefficient * values[name]
        for name, coefficient in constraint["terms"].items()
    )
    if constraint["sense"] == "==":
        violation = abs(lhs_value - constraint["rhs"])
    elif constraint["sense"] == "<=":
        violation = max(0.0, lhs_value - constraint["rhs"])
    else:
        violation = max(0.0, constraint["rhs"] - lhs_value)
    violations.append(violation)

for name, semantic_name in variable_data:
    violations.append(max(0.0, -values[name], values[name] - 1.0))

max_constraint_violation = max(violations, default=0.0)
integrality_violation = max(
    (abs(values[name] - round(values[name])) for name, semantic_name in variable_data),
    default=0.0
)

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
