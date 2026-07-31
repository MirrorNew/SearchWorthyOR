import gurobipy as gp
import json
import math

model = gp.Model("SWOR075_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
upper_bounds = {
    "x_0": 0.0,
    "x_1": 1.0,
    "x_2": 1.0,
    "x_3": 1.0,
    "x_4": 1.0,
    "x_5": 1.0,
    "x_6": 1.0
}
benefit = {
    "x_0": 1015.0,
    "x_1": 954.0,
    "x_2": 912.0,
    "x_3": 851.0,
    "x_4": 790.0,
    "x_5": 748.0,
    "x_6": 687.0
}

x = {
    name: model.addVar(
        lb=0.0,
        ub=upper_bounds[name],
        vtype=gp.GRB.BINARY,
        name=name
    )
    for name in names
}

model.setObjective(
    gp.quicksum(benefit[name] * x[name] for name in names),
    gp.GRB.MAXIMIZE
)

model.addConstr(
    gp.quicksum(x[name] for name in names) == 3.0,
    name="select_exactly_3"
)
model.addConstr(
    x["x_0"] + x["x_2"] + x["x_4"] + x["x_6"] >= 1.0,
    name="service_area_1_cover"
)
model.addConstr(
    x["x_1"] + x["x_3"] + x["x_5"] >= 1.0,
    name="service_area_2_cover"
)

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
    gp.GRB.SUBOPTIMAL: "SUBOPTIMAL"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw_values = [float(x[name].X) for name in names]
    projected_action = [int(value >= 0.5) for value in raw_values]
    objective = float(model.ObjVal)
else:
    raw_values = [0.0 for _ in names]
    projected_action = [0 for _ in names]
    objective = None

constraint_specs = [
    ({name: 1.0 for name in names}, "==", 3.0),
    ({"x_0": 1.0, "x_2": 1.0, "x_4": 1.0, "x_6": 1.0}, ">=", 1.0),
    ({"x_1": 1.0, "x_3": 1.0, "x_5": 1.0}, ">=", 1.0)
]
value_by_name = dict(zip(names, raw_values))
violations = []
for terms, sense, rhs in constraint_specs:
    lhs = sum(coefficient * value_by_name[name] for name, coefficient in terms.items())
    if sense == "<=":
        violations.append(max(0.0, lhs - rhs))
    elif sense == ">=":
        violations.append(max(0.0, rhs - lhs))
    else:
        violations.append(abs(lhs - rhs))

for name in names:
    value = value_by_name[name]
    violations.append(max(0.0, -value))
    violations.append(max(0.0, value - upper_bounds[name]))

max_constraint_violation = max(violations) if violations else 0.0
integrality_violation = max(
    abs(value - round(value)) for value in raw_values
) if raw_values else 0.0

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": float(max_constraint_violation),
    "integrality_violation": float(integrality_violation)
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
