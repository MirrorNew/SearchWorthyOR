import gurobipy
import json
import math

ir = {
    "model_id": "SWOR100",
    "world": "base",
    "sense": "max",
    "single_objective": True,
    "variables": [
        {"name": "x_0", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "建设节点A"},
        {"name": "x_1", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "建设节点B"},
        {"name": "x_2", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "建设节点C"},
        {"name": "x_3", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "建设节点D"},
        {"name": "x_4", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "建设节点E"},
        {"name": "x_5", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "建设节点F"}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1005, "x_1": 963, "x_2": 902, "x_3": 841, "x_4": 799, "x_5": 738}
    },
    "constraints": [
        {"name": "facility_count", "sense": "==", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}},
        {"name": "service_area_1_coverage", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_2": 1, "x_4": 1}},
        {"name": "service_area_2_coverage", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_3": 1, "x_5": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
}

model = gurobipy.Model(ir["model_id"])
model.Params.OutputFlag = 0
x = {}
for spec in ir["variables"]:
    x[spec["name"]] = model.addVar(
        lb=spec["lb"],
        ub=spec["ub"],
        vtype=gurobipy.GRB.BINARY,
        name=spec["name"]
    )
model.update()

objective_expr = ir["objective"]["constant"] + gurobipy.quicksum(
    coefficient * x[name] for name, coefficient in ir["objective"]["terms"].items()
)
model.setObjective(objective_expr, gurobipy.GRB.MAXIMIZE)

for constraint in ir["constraints"]:
    lhs = gurobipy.quicksum(
        coefficient * x[name] for name, coefficient in constraint["terms"].items()
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
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
    gurobipy.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: x[name].X for name in x}
    projected_action = [1 if values[name] >= 0.5 else 0 for name in ir["action_projection"]]
    integrality_violation = max(abs(value - round(value)) for value in values.values())
    violations = []
    for constraint in ir["constraints"]:
        lhs_value = sum(coefficient * values[name] for name, coefficient in constraint["terms"].items())
        rhs = constraint["rhs"]
        if constraint["sense"] == "<=":
            violation = max(0.0, lhs_value - rhs)
        elif constraint["sense"] == ">=":
            violation = max(0.0, rhs - lhs_value)
        else:
            violation = abs(lhs_value - rhs)
        violations.append(violation)
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations) if violations else 0.0,
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0 for _ in ir["action_projection"]],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))