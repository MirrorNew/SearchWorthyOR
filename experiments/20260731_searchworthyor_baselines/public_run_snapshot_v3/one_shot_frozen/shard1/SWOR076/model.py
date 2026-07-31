import gurobipy as gp
import json
import math

ir = {
    "model_id": "SWOR076_patched",
    "sense": "max",
    "variables": [
        {"name": "x_0", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_1", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_2", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_3", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_4", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_5", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_6", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_7", "vartype": "B", "lb": 0, "ub": 1}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1010, "x_1": 949, "x_2": 907, "x_3": 846, "x_4": 804, "x_5": 743, "x_6": 682, "x_7": 640}
    },
    "constraints": [
        {"name": "select_exactly_3", "sense": "==", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1, "x_7": 1}},
        {"name": "emergency_coverage", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}},
        {"name": "continuity_coverage", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_2": 1}},
        {"name": "specialty_coverage", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_2": 1}},
        {"name": "terminal_backup_mutex", "sense": "<=", "rhs": 1, "terms": {"x_6": 1, "x_7": 1}},
        {"name": "compliance_A_implies_not_B", "sense": "<=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
}

model = gp.Model(ir["model_id"])
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0
variables = {}
for spec in ir["variables"]:
    variables[spec["name"]] = model.addVar(
        vtype=gp.GRB.BINARY,
        lb=spec["lb"],
        ub=spec["ub"],
        name=spec["name"]
    )
model.update()

objective = ir["objective"]["constant"] + gp.quicksum(
    coefficient * variables[name]
    for name, coefficient in ir["objective"]["terms"].items()
)
model.setObjective(objective, gp.GRB.MAXIMIZE)

for constraint in ir["constraints"]:
    lhs = gp.quicksum(
        coefficient * variables[name]
        for name, coefficient in constraint["terms"].items()
    )
    if constraint["sense"] == "<=":
        model.addConstr(lhs <= constraint["rhs"], name=constraint["name"])
    elif constraint["sense"] == ">=":
        model.addConstr(lhs >= constraint["rhs"], name=constraint["name"])
    elif constraint["sense"] == "==":
        model.addConstr(lhs == constraint["rhs"], name=constraint["name"])
    else:
        raise ValueError("Unsupported constraint sense")

model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, "STATUS_" + str(model.Status))

if model.SolCount > 0:
    raw_values = {name: float(variable.X) for name, variable in variables.items()}
    projected_action = [int(raw_values[name] >= 0.5) for name in ir["action_projection"]]
    integrality_violation = max(
        abs(value - round(value)) for value in raw_values.values()
    )
    constraint_violations = []
    for constraint in ir["constraints"]:
        lhs_value = sum(
            coefficient * raw_values[name]
            for name, coefficient in constraint["terms"].items()
        )
        if constraint["sense"] == "<=":
            violation = max(0.0, lhs_value - constraint["rhs"])
        elif constraint["sense"] == ">=":
            violation = max(0.0, constraint["rhs"] - lhs_value)
        else:
            violation = abs(lhs_value - constraint["rhs"])
        constraint_violations.append(violation)
    result = {
        "status": status,
        "objective": float(model.ObjVal) if math.isfinite(float(model.ObjVal)) else None,
        "projected_action": projected_action,
        "max_constraint_violation": max(constraint_violations) if constraint_violations else 0.0,
        "integrality_violation": integrality_violation
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
