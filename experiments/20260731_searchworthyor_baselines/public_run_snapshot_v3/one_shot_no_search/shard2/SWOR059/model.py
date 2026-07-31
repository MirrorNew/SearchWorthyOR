import gurobipy as gp
import json
import math

# [BASE_DATA]
candidate_facts = [
    {"candidate": "路径包A", "benefit": 1000, "resource_points": 1, "category": "基础类别"},
    {"candidate": "路径包B", "benefit": 958, "resource_points": 2, "category": "基础类别"},
    {"candidate": "路径包C", "benefit": 897, "resource_points": 3, "category": "基础类别"},
    {"candidate": "路径包D", "benefit": 855, "resource_points": 4, "category": "基础类别"},
    {"candidate": "路径包E", "benefit": 794, "resource_points": 1, "category": "保障类别1"},
    {"candidate": "路径包F", "benefit": 752, "resource_points": 2, "category": "保障类别2"}
]
action_projection = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
objective_coeffs = {
    "x_0": 1000, "x_1": 958, "x_2": 897,
    "x_3": 855, "x_4": 794, "x_5": 752
}
constraint_specs = [
    {"name": "transport_chain_segment_1_exactly_one", "sense": "==", "rhs": 1.0, "terms": {"x_0": 1.0, "x_3": 1.0}},
    {"name": "transport_chain_segment_2_exactly_one", "sense": "==", "rhs": 1.0, "terms": {"x_1": 1.0, "x_4": 1.0}},
    {"name": "transport_chain_segment_3_exactly_one", "sense": "==", "rhs": 1.0, "terms": {"x_2": 1.0, "x_5": 1.0}}
]

model = gp.Model("SWOR059_base")
model.Params.OutputFlag = 0

# [VARIABLES]
x = {
    name: model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=name)
    for name in action_projection
}

# [OBJECTIVE]
model.setObjective(
    gp.quicksum(objective_coeffs[name] * x[name] for name in action_projection),
    gp.GRB.MAXIMIZE
)

# [CONSTRAINT_SEGMENT_1]
model.addConstr(x["x_0"] + x["x_3"] == 1, name="transport_chain_segment_1_exactly_one")
# [CONSTRAINT_SEGMENT_2]
model.addConstr(x["x_1"] + x["x_4"] == 1, name="transport_chain_segment_2_exactly_one")
# [CONSTRAINT_SEGMENT_3]
model.addConstr(x["x_2"] + x["x_5"] == 1, name="transport_chain_segment_3_exactly_one")

# [SOLVE_AND_REPORT]
model.optimize()
status = int(model.Status)
has_solution = model.SolCount > 0

if has_solution:
    raw_values = {name: float(x[name].X) for name in action_projection}
    projected_action = [int(round(raw_values[name])) for name in action_projection]
    objective = float(model.ObjVal)

    constraint_violations = []
    for spec in constraint_specs:
        lhs = sum(coef * raw_values[name] for name, coef in spec["terms"].items())
        rhs = spec["rhs"]
        if spec["sense"] == "==":
            violation = abs(lhs - rhs)
        elif spec["sense"] == "<=":
            violation = max(0.0, lhs - rhs)
        else:
            violation = max(0.0, rhs - lhs)
        constraint_violations.append(violation)

    max_constraint_violation = max(constraint_violations) if constraint_violations else 0.0
    integrality_violation = max(
        abs(raw_values[name] - round(raw_values[name]))
        for name in action_projection
    )
else:
    projected_action = [0 for _ in action_projection]
    objective = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
