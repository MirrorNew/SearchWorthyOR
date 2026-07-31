import gurobipy
import json
import math

model = gurobipy.Model("SWOR034_patched")
model.Params.OutputFlag = 0

action_projection = [f"x_{i}" for i in range(8)]
x = {
    name: model.addVar(vtype=gurobipy.GRB.BINARY, lb=0.0, ub=1.0, name=name)
    for name in action_projection
}

# REGION objective
objective_terms = {
    "x_0": 1000.0,
    "x_1": 958.0,
    "x_2": 897.0,
    "x_3": 855.0,
    "x_4": 794.0,
    "x_5": 752.0,
    "x_6": 691.0,
    "x_7": 630.0,
}
model.setObjective(
    gurobipy.quicksum(coef * x[name] for name, coef in objective_terms.items()),
    gurobipy.GRB.MAXIMIZE,
)

# REGION constraints
constraint_specs = [
    {"name": "c_max_modules", "sense": "<=", "rhs": 3.0, "terms": {name: 1.0 for name in action_projection}},
    {"name": "c_zone_1_connectivity", "sense": ">=", "rhs": 1.0, "terms": {"x_0": 1.0, "x_3": 1.0, "x_6": 1.0}},
    {"name": "c_zone_2_connectivity", "sense": ">=", "rhs": 1.0, "terms": {"x_1": 1.0, "x_4": 1.0, "x_7": 1.0}},
    {"name": "c_zone_3_connectivity", "sense": ">=", "rhs": 1.0, "terms": {"x_2": 1.0, "x_5": 1.0}},
    {"name": "c_A_requires_B_or_E", "sense": "<=", "rhs": 0.0, "terms": {"x_0": 1.0, "x_1": -1.0, "x_4": -1.0}},
    {"name": "c_policy_A_B_mutex", "sense": "<=", "rhs": 1.0, "terms": {"x_0": 1.0, "x_1": 1.0}},
]

for spec in constraint_specs:
    lhs = gurobipy.quicksum(coef * x[name] for name, coef in spec["terms"].items())
    if spec["sense"] == "<=":
        model.addConstr(lhs <= spec["rhs"], name=spec["name"])
    elif spec["sense"] == ">=":
        model.addConstr(lhs >= spec["rhs"], name=spec["name"])
    else:
        model.addConstr(lhs == spec["rhs"], name=spec["name"])

# REGION solve_and_report
model.optimize()
status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
    gurobipy.GRB.INTERRUPTED: "INTERRUPTED",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: float(x[name].X) for name in action_projection}
    projected_action = [int(round(values[name])) for name in action_projection]
    violations = []
    for spec in constraint_specs:
        lhs_value = sum(coef * values[name] for name, coef in spec["terms"].items())
        if spec["sense"] == "<=":
            violation = max(0.0, lhs_value - spec["rhs"])
        elif spec["sense"] == ">=":
            violation = max(0.0, spec["rhs"] - lhs_value)
        else:
            violation = abs(lhs_value - spec["rhs"])
        violations.append(violation)
    max_constraint_violation = float(max(violations, default=0.0))
    integrality_violation = float(max(abs(value - round(value)) for value in values.values()))
    objective = float(model.ObjVal)
else:
    objective = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False))
