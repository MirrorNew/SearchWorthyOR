import gurobipy as gp
import json
import math

patched_ir = {
    "model_id": "SWOR064",
    "world": "patched",
    "sense": "max",
    "single_objective": True,
    "variables": [
        {"name": "x_0", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "节点A是否建设"},
        {"name": "x_1", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "节点B是否建设"},
        {"name": "x_2", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "节点C是否建设"},
        {"name": "x_3", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "节点D是否建设"},
        {"name": "x_4", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "节点E是否建设"},
        {"name": "x_5", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "节点F是否建设"},
        {"name": "x_6", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "节点G是否建设"},
        {"name": "x_7", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "节点H是否建设"}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1001, "x_1": 959, "x_2": 898, "x_3": 856, "x_4": 795, "x_5": 753, "x_6": 692, "x_7": 631}
    },
    "constraints": [
        {"name": "select_exactly_3", "sense": "==", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1, "x_7": 1}},
        {"name": "service_area_1_min_coverage", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_2": 1, "x_4": 1, "x_6": 1}},
        {"name": "service_area_2_min_coverage", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_3": 1, "x_5": 1, "x_7": 1}},
        {"name": "core_candidates_min_2", "sense": ">=", "rhs": 2, "terms": {"x_0": 1, "x_1": 1, "x_2": 1}},
        {"name": "incompatibility_ab", "sense": "<=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
}

model = gp.Model(patched_ir["model_id"])
model.Params.OutputFlag = 0

# code_region: variables
variables = {}
for specification in patched_ir["variables"]:
    variables[specification["name"]] = model.addVar(
        lb=specification["lb"],
        ub=specification["ub"],
        vtype=gp.GRB.BINARY,
        name=specification["name"]
    )
model.update()

# code_region: objective/network_benefit
objective_expression = gp.LinExpr()
objective_expression += float(patched_ir["objective"]["constant"])
for variable_name, coefficient in patched_ir["objective"]["terms"].items():
    objective_expression += float(coefficient) * variables[variable_name]
model.setObjective(objective_expression, gp.GRB.MAXIMIZE)

# code_region: constraints/base_and_policy
for specification in patched_ir["constraints"]:
    expression = gp.LinExpr()
    for variable_name, coefficient in specification["terms"].items():
        expression += float(coefficient) * variables[variable_name]
    if specification["sense"] == "<=":
        model.addConstr(expression <= float(specification["rhs"]), name=specification["name"])
    elif specification["sense"] == ">=":
        model.addConstr(expression >= float(specification["rhs"]), name=specification["name"])
    elif specification["sense"] == "==":
        model.addConstr(expression == float(specification["rhs"]), name=specification["name"])
    else:
        raise ValueError("Unsupported constraint sense")

model.optimize()

if model.Status == gp.GRB.OPTIMAL:
    status = "OPTIMAL"
elif model.Status == gp.GRB.INFEASIBLE:
    status = "INFEASIBLE"
elif model.Status == gp.GRB.UNBOUNDED:
    status = "UNBOUNDED"
elif model.Status == gp.GRB.INF_OR_UNBD:
    status = "INF_OR_UNBD"
else:
    status = str(model.Status)

if model.SolCount > 0:
    values = {name: float(variable.X) for name, variable in variables.items()}
    projected_action = [int(values[name] >= 0.5) for name in patched_ir["action_projection"]]
    objective_value = float(model.ObjVal)
    max_constraint_violation = 0.0
    for specification in patched_ir["constraints"]:
        lhs = sum(float(coefficient) * values[name] for name, coefficient in specification["terms"].items())
        rhs = float(specification["rhs"])
        if specification["sense"] == "<=":
            violation = max(0.0, lhs - rhs)
        elif specification["sense"] == ">=":
            violation = max(0.0, rhs - lhs)
        else:
            violation = abs(lhs - rhs)
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(min(abs(value), abs(value - 1.0)) for value in values.values())
else:
    objective_value = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective_value,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
