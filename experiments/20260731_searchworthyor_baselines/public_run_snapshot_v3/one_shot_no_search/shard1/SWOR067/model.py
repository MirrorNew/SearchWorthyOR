import gurobipy as gp
import json
import math

patched_ir = {
    "model_id": "SWOR067_base",
    "world": {
        "decision_time": "2026-05-29",
        "entity": "和岚医疗健康运营有限公司（海桥经营辖区（合成）青浦单元）",
        "jurisdiction": "海桥经营辖区（合成）"
    },
    "sense": "max",
    "single_objective": True,
    "variables": [
        {"name": "x_0", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "启用服务单元A"},
        {"name": "x_1", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "启用服务单元B"},
        {"name": "x_2", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "启用服务单元C"},
        {"name": "x_3", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "启用服务单元D"},
        {"name": "x_4", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "启用服务单元E"},
        {"name": "x_5", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "启用服务单元F"}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1002, "x_1": 960, "x_2": 899, "x_3": 857, "x_4": 796, "x_5": 735}
    },
    "constraints": [
        {"name": "enable_exactly_three", "sense": "==", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}},
        {"name": "emergency_coverage", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}},
        {"name": "continuity_of_care_coverage", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_2": 1}},
        {"name": "specialty_service_coverage", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_2": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
}

model = gp.Model(patched_ir["model_id"])
model.Params.OutputFlag = 0
variables = {}
for spec in patched_ir["variables"]:
    variables[spec["name"]] = model.addVar(
        lb=spec["lb"],
        ub=spec["ub"],
        vtype=gp.GRB.BINARY,
        name=spec["name"]
    )
model.update()

objective = gp.LinExpr(patched_ir["objective"]["constant"])
for name, coefficient in patched_ir["objective"]["terms"].items():
    objective += coefficient * variables[name]
model.setObjective(objective, gp.GRB.MAXIMIZE)

for constraint in patched_ir["constraints"]:
    lhs = gp.quicksum(coefficient * variables[name] for name, coefficient in constraint["terms"].items())
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
    values = {name: variable.X for name, variable in variables.items()}
    projected_action = [int(round(values[name])) for name in patched_ir["action_projection"]]
    max_constraint_violation = 0.0
    for constraint in patched_ir["constraints"]:
        lhs_value = sum(coefficient * values[name] for name, coefficient in constraint["terms"].items())
        if constraint["sense"] == "<=":
            violation = max(0.0, lhs_value - constraint["rhs"])
        elif constraint["sense"] == ">=":
            violation = max(0.0, constraint["rhs"] - lhs_value)
        else:
            violation = abs(lhs_value - constraint["rhs"])
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(abs(value - round(value)) for value in values.values())
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max_constraint_violation,
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

print(json.dumps(result, ensure_ascii=False, allow_nan=False))