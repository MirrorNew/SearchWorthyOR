import gurobipy as gp
import json

# REGION_PATCHED_IR
patched_ir = {
    "model_id": "SWOR036_patched",
    "sense": "max",
    "variables": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1009, "x_1": 948, "x_2": 906, "x_3": 845, "x_4": 803, "x_5": 742}
    },
    "constraints": [
        {"name": "max_three_modes", "sense": "<=", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}},
        {"name": "equipment_capacity", "sense": "<=", "rhs": 6, "terms": {"x_0": 1, "x_1": 2, "x_2": 3, "x_3": 4, "x_4": 1, "x_5": 2}},
        {"name": "exactly_one_B_E_F", "sense": "==", "rhs": 1, "terms": {"x_1": 1, "x_4": 1, "x_5": 1}},
        {"name": "policy_mode_A_ineligible", "sense": "==", "rhs": 0, "terms": {"x_0": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
}

model = gp.Model(patched_ir["model_id"])
model.Params.OutputFlag = 0

# REGION_VARIABLES
variables = {
    name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name)
    for name in patched_ir["variables"]
}
model.update()

# REGION_OBJECTIVE
objective = patched_ir["objective"]["constant"] + gp.quicksum(
    coefficient * variables[name]
    for name, coefficient in patched_ir["objective"]["terms"].items()
)
model.setObjective(objective, gp.GRB.MAXIMIZE)

# REGION_CONSTRAINTS
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

# REGION_SOLVE_AND_REPORT
model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: variables[name].X for name in patched_ir["variables"]}
    projected_action = [int(round(values[name])) for name in patched_ir["action_projection"]]
    max_constraint_violation = 0.0
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
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(
        abs(value - round(value)) for value in values.values()
    )
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
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, sort_keys=True))
