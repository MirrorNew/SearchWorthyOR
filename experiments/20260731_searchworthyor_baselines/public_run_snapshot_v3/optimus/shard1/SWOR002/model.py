import gurobipy as gp
import json

patched_ir = {
    "model_id": "SWOR002_patched",
    "world": "patched",
    "sense": "max",
    "single_objective": True,
    "variables": [
        {"name": "x_0", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "服务模块A"},
        {"name": "x_1", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "服务模块B"},
        {"name": "x_2", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "服务模块C"},
        {"name": "x_3", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "服务模块D"},
        {"name": "x_4", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "服务模块E"},
        {"name": "x_5", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "服务模块F"},
        {"name": "x_6", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "服务模块G"}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1008, "x_1": 947, "x_2": 905, "x_3": 844, "x_4": 802, "x_5": 741, "x_6": 699}
    },
    "constraints": [
        {"name": "maximum_enabled_modules", "sense": "<=", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1}},
        {"name": "zone_1_connectivity", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_3": 1, "x_6": 1}},
        {"name": "zone_2_connectivity", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_4": 1}},
        {"name": "zone_3_connectivity", "sense": ">=", "rhs": 1, "terms": {"x_2": 1, "x_5": 1}},
        {"name": "primary_access_backhaul", "sense": ">=", "rhs": 0, "terms": {"x_0": -1, "x_1": 1, "x_4": 1}},
        {"name": "terminal_backup_exclusivity", "sense": "<=", "rhs": 1, "terms": {"x_5": 1, "x_6": 1}},
        {"name": "policy_guarantee_minimum", "sense": ">=", "rhs": 1, "terms": {"x_5": 1, "x_6": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
}

model = gp.Model(patched_ir["model_id"])
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

variables = {}
for spec in patched_ir["variables"]:
    variables[spec["name"]] = model.addVar(
        lb=spec["lb"],
        ub=spec["ub"],
        vtype=gp.GRB.BINARY,
        name=spec["name"]
    )

objective = gp.quicksum(
    coefficient * variables[name]
    for name, coefficient in patched_ir["objective"]["terms"].items()
) + patched_ir["objective"]["constant"]
model.setObjective(objective, gp.GRB.MAXIMIZE)

for constraint in patched_ir["constraints"]:
    lhs = gp.quicksum(
        coefficient * variables[name]
        for name, coefficient in constraint["terms"].items()
    )
    if constraint["sense"] == "<=":
        model.addConstr(lhs <= constraint["rhs"], name=constraint["name"])
    elif constraint["sense"] == ">=":
        model.addConstr(lhs >= constraint["rhs"], name=constraint["name"])
    else:
        model.addConstr(lhs == constraint["rhs"], name=constraint["name"])

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
status = status_names.get(model.Status, "STATUS_" + str(model.Status))

if model.SolCount > 0:
    values = {name: variables[name].X for name in variables}
    projected_action = [int(round(values[name])) for name in patched_ir["action_projection"]]
    integrality_violation = max(abs(value - round(value)) for value in values.values())
    violations = []
    for constraint in patched_ir["constraints"]:
        lhs_value = sum(
            coefficient * values[name]
            for name, coefficient in constraint["terms"].items()
        )
        if constraint["sense"] == "<=":
            violation = max(0.0, lhs_value - constraint["rhs"])
        elif constraint["sense"] == ">=":
            violation = max(0.0, constraint["rhs"] - lhs_value)
        else:
            violation = abs(lhs_value - constraint["rhs"])
        violations.append(violation)
    max_constraint_violation = max(violations) if violations else 0.0
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": float(max_constraint_violation),
        "integrality_violation": float(integrality_violation)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0 for _ in patched_ir["action_projection"]],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, sort_keys=True))
