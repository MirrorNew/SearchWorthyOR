import gurobipy as gp
import json
import math

# REGION: PATCHED_IR
patched_ir = {
    "model_id": "SWOR039_patched",
    "sense": "max",
    "variables": [
        {"name": "x_0", "semantic_name": "路径包A"},
        {"name": "x_1", "semantic_name": "路径包B"},
        {"name": "x_2", "semantic_name": "路径包C"},
        {"name": "x_3", "semantic_name": "路径包D"},
        {"name": "x_4", "semantic_name": "路径包E"},
        {"name": "x_5", "semantic_name": "路径包F"},
        {"name": "x_6", "semantic_name": "路径包G"}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1005, "x_1": 963, "x_2": 902, "x_3": 841, "x_4": 799, "x_5": 738, "x_6": 696}
    },
    "constraints": [
        {"name": "segment_1_exactly_one", "sense": "==", "rhs": 1, "terms": {"x_0": 1, "x_3": 1, "x_6": 1}},
        {"name": "segment_2_exactly_one", "sense": "==", "rhs": 1, "terms": {"x_1": 1, "x_4": 1}},
        {"name": "segment_3_exactly_one", "sense": "==", "rhs": 1, "terms": {"x_2": 1, "x_5": 1}},
        {"name": "minimum_core_selections", "sense": ">=", "rhs": 2, "terms": {"x_0": 1, "x_1": 1, "x_2": 1}},
        {"name": "policy_A_prohibits_B", "sense": "<=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
}

# REGION: VARIABLES
model = gp.Model(patched_ir["model_id"])
model.Params.OutputFlag = 0
model.Params.Threads = 1
model.Params.Seed = 0
model.Params.PoolSearchMode = 2
model.Params.PoolSolutions = 128
model.Params.PoolGap = 0.0
x = {
    item["name"]: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=item["name"])
    for item in patched_ir["variables"]
}

# REGION: OBJECTIVE
objective = gp.LinExpr(patched_ir["objective"]["constant"])
for name, coefficient in patched_ir["objective"]["terms"].items():
    objective += coefficient * x[name]
model.setObjective(objective, gp.GRB.MAXIMIZE)

# REGION: CONSTRAINTS
for constraint in patched_ir["constraints"]:
    lhs = gp.quicksum(coefficient * x[name] for name, coefficient in constraint["terms"].items())
    if constraint["sense"] == "==":
        model.addConstr(lhs == constraint["rhs"], name=constraint["name"])
    elif constraint["sense"] == ">=":
        model.addConstr(lhs >= constraint["rhs"], name=constraint["name"])
    else:
        model.addConstr(lhs <= constraint["rhs"], name=constraint["name"])

# REGION: SOLVE_AND_REPORT
model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.SUBOPTIMAL: "SUBOPTIMAL",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))
objective_value = None
projected_action = []
optimal_actions = []
max_constraint_violation = None
integrality_violation = None

if model.SolCount > 0:
    objective_value = float(model.ObjVal)
    for solution_number in range(model.SolCount):
        model.Params.SolutionNumber = solution_number
        if math.isclose(float(model.PoolObjVal), objective_value, rel_tol=1e-9, abs_tol=1e-6):
            action = [int(round(x[name].Xn)) for name in patched_ir["action_projection"]]
            if action not in optimal_actions:
                optimal_actions.append(action)
    optimal_actions.sort()
    projected_action = optimal_actions[0]
    values = dict(zip(patched_ir["action_projection"], projected_action))
    violations = []
    for constraint in patched_ir["constraints"]:
        lhs_value = sum(coefficient * values[name] for name, coefficient in constraint["terms"].items())
        rhs = constraint["rhs"]
        if constraint["sense"] == "==":
            violations.append(abs(lhs_value - rhs))
        elif constraint["sense"] == ">=":
            violations.append(max(0.0, rhs - lhs_value))
        else:
            violations.append(max(0.0, lhs_value - rhs))
    max_constraint_violation = float(max(violations, default=0.0))
    integrality_violation = float(max((abs(values[name] - round(values[name])) for name in values), default=0.0))

result = {
    "status": status,
    "objective": objective_value,
    "projected_action": projected_action,
    "optimal_actions": optimal_actions,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
