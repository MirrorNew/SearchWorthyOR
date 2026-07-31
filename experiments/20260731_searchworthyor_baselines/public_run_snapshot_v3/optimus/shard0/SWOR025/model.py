import gurobipy as gp
import json
import math

ir = {
    "model_id": "SWOR025_patched",
    "world": "applicable_policy_world_DOC-B3A50FEB36E1679E",
    "sense": "max",
    "single_objective": True,
    "variables": [
        {"name": "x_0", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "班次A"},
        {"name": "x_1", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "班次B"},
        {"name": "x_2", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "班次C"},
        {"name": "x_3", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "班次D"},
        {"name": "x_4", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "班次E"},
        {"name": "x_5", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "班次F"},
        {"name": "x_6", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "班次G"}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1006, "x_1": 964, "x_2": 903, "x_3": 842, "x_4": 800, "x_5": 739, "x_6": 697}
    },
    "constraints": [
        {"name": "required_shift_count", "sense": "==", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1}},
        {"name": "period_1_coverage", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_3": 1, "x_6": 1}},
        {"name": "period_2_coverage", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_4": 1}},
        {"name": "period_3_coverage", "sense": ">=", "rhs": 1, "terms": {"x_2": 1, "x_5": 1}},
        {"name": "local_conflict_F_G", "sense": "<=", "rhs": 1, "terms": {"x_5": 1, "x_6": 1}},
        {"name": "policy_conflict_A_B", "sense": "<=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
}

model = gp.Model(ir["model_id"])
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0
model.Params.Seed = 0
model.Params.Threads = 1
model.Params.PoolSearchMode = 2
model.Params.PoolSolutions = 100
model.Params.PoolGap = 0.0

x = {}
for spec in ir["variables"]:
    x[spec["name"]] = model.addVar(
        lb=spec["lb"],
        ub=spec["ub"],
        vtype=gp.GRB.BINARY,
        name=spec["name"]
    )
model.update()

objective = ir["objective"]["constant"] + gp.quicksum(
    coefficient * x[name] for name, coefficient in ir["objective"]["terms"].items()
)
model.setObjective(objective, gp.GRB.MAXIMIZE)

for spec in ir["constraints"]:
    lhs = gp.quicksum(coefficient * x[name] for name, coefficient in spec["terms"].items())
    if spec["sense"] == "<=":
        model.addConstr(lhs <= spec["rhs"], name=spec["name"])
    elif spec["sense"] == ">=":
        model.addConstr(lhs >= spec["rhs"], name=spec["name"])
    elif spec["sense"] == "==":
        model.addConstr(lhs == spec["rhs"], name=spec["name"])
    else:
        raise ValueError("Unsupported constraint sense")

model.optimize()

has_solution = model.SolCount > 0
if has_solution:
    projected_action = [int(x[name].X >= 0.5) for name in ir["action_projection"]]
    objective_value = float(model.ObjVal)

    max_constraint_violation = 0.0
    for constraint in model.getConstrs():
        row = model.getRow(constraint)
        lhs_value = sum(row.getCoeff(j) * row.getVar(j).X for j in range(row.size()))
        if constraint.Sense == "<":
            violation = max(0.0, lhs_value - constraint.RHS)
        elif constraint.Sense == ">":
            violation = max(0.0, constraint.RHS - lhs_value)
        else:
            violation = abs(lhs_value - constraint.RHS)
        max_constraint_violation = max(max_constraint_violation, violation)
    for variable in model.getVars():
        max_constraint_violation = max(
            max_constraint_violation,
            max(0.0, variable.LB - variable.X),
            max(0.0, variable.X - variable.UB)
        )
    integrality_violation = max(abs(variable.X - round(variable.X)) for variable in model.getVars())

    all_optimal_projected_actions = []
    for solution_number in range(model.SolCount):
        model.Params.SolutionNumber = solution_number
        if math.isclose(model.PoolObjVal, model.ObjVal, rel_tol=0.0, abs_tol=1e-6):
            action = [int(x[name].Xn >= 0.5) for name in ir["action_projection"]]
            if action not in all_optimal_projected_actions:
                all_optimal_projected_actions.append(action)
    all_optimal_projected_actions.sort()
else:
    projected_action = [0 for _ in ir["action_projection"]]
    objective_value = None
    max_constraint_violation = None
    integrality_violation = None
    all_optimal_projected_actions = []

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": objective_value,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
    "all_optimal_projected_actions": all_optimal_projected_actions
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
