import gurobipy as gp
import json
import math

ir = {
    "model_id": "SWOR040_patched",
    "sense": "max",
    "single_objective": True,
    "variables": [
        {"name": "x_0", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_1", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_2", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_3", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_4", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_5", "vartype": "B", "lb": 0, "ub": 1}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1011, "x_1": 950, "x_2": 908, "x_3": 847, "x_4": 805, "x_5": 744}
    },
    "constraints": [
        {"name": "build_exactly_3", "sense": "==", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}},
        {"name": "cover_service_area_1", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_2": 1, "x_4": 1}},
        {"name": "cover_service_area_2", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_3": 1, "x_5": 1}},
        {"name": "enable_at_least_2_core_nodes", "sense": ">=", "rhs": 2, "terms": {"x_0": 1, "x_1": 1, "x_2": 1}},
        {"name": "policy_mutual_exclusion_A_B", "sense": "<=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
}

env = gp.Env(empty=True)
env.setParam("OutputFlag", 0)
env.start()
model = gp.Model(ir["model_id"], env=env)
variables = {}
for spec in ir["variables"]:
    variables[spec["name"]] = model.addVar(
        lb=spec["lb"],
        ub=spec["ub"],
        vtype=gp.GRB.BINARY,
        name=spec["name"]
    )
model.update()

objective = gp.LinExpr(ir["objective"]["constant"])
for name, coefficient in ir["objective"]["terms"].items():
    objective += coefficient * variables[name]
model.setObjective(objective, gp.GRB.MAXIMIZE)

for spec in ir["constraints"]:
    expression = gp.quicksum(coefficient * variables[name] for name, coefficient in spec["terms"].items())
    if spec["sense"] == "<=":
        model.addConstr(expression <= spec["rhs"], name=spec["name"])
    elif spec["sense"] == ">=":
        model.addConstr(expression >= spec["rhs"], name=spec["name"])
    else:
        model.addConstr(expression == spec["rhs"], name=spec["name"])

model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.SUBOPTIMAL: "SUBOPTIMAL"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: variables[name].X for name in variables}
    projected_action = [int(round(values[name])) for name in ir["action_projection"]]
    objective_value = float(model.ObjVal)
    if not math.isfinite(objective_value):
        objective_value = None
    max_constraint_violation = 0.0
    for spec in ir["constraints"]:
        lhs = sum(coefficient * values[name] for name, coefficient in spec["terms"].items())
        if spec["sense"] == "<=":
            violation = max(0.0, lhs - spec["rhs"])
        elif spec["sense"] == ">=":
            violation = max(0.0, spec["rhs"] - lhs)
        else:
            violation = abs(lhs - spec["rhs"])
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(abs(value - round(value)) for value in values.values())
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
model.dispose()
env.dispose()
