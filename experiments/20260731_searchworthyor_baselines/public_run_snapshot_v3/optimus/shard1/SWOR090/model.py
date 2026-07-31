import gurobipy as gp
import json
import math

# REGION: PATCHED_IR_DATA
variable_specs = [
    {"name": "x_0", "semantic_name": "策略包A", "lb": 0, "ub": 1},
    {"name": "x_1", "semantic_name": "策略包B", "lb": 0, "ub": 1},
    {"name": "x_2", "semantic_name": "策略包C", "lb": 0, "ub": 1},
    {"name": "x_3", "semantic_name": "策略包D", "lb": 0, "ub": 1},
    {"name": "x_4", "semantic_name": "策略包E", "lb": 0, "ub": 1},
    {"name": "x_5", "semantic_name": "策略包F", "lb": 0, "ub": 1},
    {"name": "x_6", "semantic_name": "策略包G", "lb": 0, "ub": 1},
    {"name": "x_7", "semantic_name": "策略包H", "lb": 0, "ub": 1}
]
objective_constant = 0
objective_terms = {"x_0": 1005, "x_1": 963, "x_2": 902, "x_3": 841, "x_4": 799, "x_5": 738, "x_6": 696, "x_7": 635}
constraint_specs = [
    {"name": "position_count", "sense": "==", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1, "x_7": 1}},
    {"name": "capital_capacity", "sense": "<=", "rhs": 12, "terms": {"x_0": 2, "x_1": 3, "x_2": 4, "x_3": 1, "x_4": 2, "x_5": 3, "x_6": 4, "x_7": 1}},
    {"name": "risk_capacity", "sense": "<=", "rhs": 15, "terms": {"x_0": 4, "x_1": 1, "x_2": 3, "x_3": 5, "x_4": 2, "x_5": 4, "x_6": 1, "x_7": 3}},
    {"name": "core_or_backup", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_3": 1}},
    {"name": "external_conflict_A_B", "sense": "<=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}}
]
action_projection = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]

# REGION: VARIABLES
model = gp.Model("SWOR090")
model.Params.OutputFlag = 0
x = {}
for spec in variable_specs:
    x[spec["name"]] = model.addVar(lb=spec["lb"], ub=spec["ub"], vtype=gp.GRB.BINARY, name=spec["name"])
model.update()

# REGION: OBJECTIVE
objective_expr = objective_constant + gp.quicksum(coef * x[name] for name, coef in objective_terms.items())
model.setObjective(objective_expr, gp.GRB.MAXIMIZE)

# REGION: BASE_CONSTRAINTS_AND_EXTERNAL_PATCH
for spec in constraint_specs:
    lhs = gp.quicksum(coef * x[name] for name, coef in spec["terms"].items())
    if spec["sense"] == "<=":
        model.addConstr(lhs <= spec["rhs"], name=spec["name"])
    elif spec["sense"] == ">=":
        model.addConstr(lhs >= spec["rhs"], name=spec["name"])
    else:
        model.addConstr(lhs == spec["rhs"], name=spec["name"])

# REGION: SOLVE_AND_REPORT
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
    raw_values = {name: x[name].X for name in action_projection}
    projected_action = [int(round(raw_values[name])) for name in action_projection]
    objective = objective_constant + sum(objective_terms[name] * projected_action[i] for i, name in enumerate(action_projection))
    max_constraint_violation = 0.0
    for spec in constraint_specs:
        lhs_value = sum(coef * raw_values[name] for name, coef in spec["terms"].items())
        if spec["sense"] == "<=":
            violation = max(0.0, lhs_value - spec["rhs"])
        elif spec["sense"] == ">=":
            violation = max(0.0, spec["rhs"] - lhs_value)
        else:
            violation = abs(lhs_value - spec["rhs"])
        max_constraint_violation = max(max_constraint_violation, violation)
    for spec in variable_specs:
        value = raw_values[spec["name"]]
        max_constraint_violation = max(max_constraint_violation, max(0.0, spec["lb"] - value, value - spec["ub"]))
    integrality_violation = max(abs(raw_values[name] - round(raw_values[name])) for name in action_projection)
else:
    projected_action = [0 for _ in action_projection]
    objective = None
    max_constraint_violation = None
    integrality_violation = None

def clean_number(value):
    if value is None:
        return None
    if math.isfinite(value) and abs(value - round(value)) <= 1e-9:
        return int(round(value))
    return float(value)

result = {
    "status": status,
    "objective": clean_number(objective),
    "projected_action": projected_action,
    "max_constraint_violation": clean_number(max_constraint_violation),
    "integrality_violation": clean_number(integrality_violation)
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))