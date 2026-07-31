import gurobipy as gp
import json
import math

model = gp.Model("SWOR008")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

objective_coefficients = [1016, 955, 894, 852, 791, 749, 688]
model.setObjective(
    gp.quicksum(objective_coefficients[i] * x[i] for i in range(7)),
    gp.GRB.MAXIMIZE,
)

constraint_data = [
    ("build_exactly_3_nodes", "==", 3.0, {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0}),
    ("service_area_1_coverage", ">=", 1.0, {0: 1.0, 2: 1.0, 4: 1.0, 6: 1.0}),
    ("service_area_2_coverage_frozen", ">=", 1.0, {1: 1.0, 3: 1.0, 5: 1.0}),
    ("exactly_one_of_B_E_G", "==", 1.0, {1: 1.0, 4: 1.0, 6: 1.0}),
]

for name, sense, rhs, terms in constraint_data:
    expression = gp.quicksum(coefficient * x[index] for index, coefficient in terms.items())
    if sense == "<=":
        model.addConstr(expression <= rhs, name=name)
    elif sense == ">=":
        model.addConstr(expression >= rhs, name=name)
    else:
        model.addConstr(expression == rhs, name=name)

model.optimize()

status_names = {
    gp.GRB.LOADED: "LOADED",
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.CUTOFF: "CUTOFF",
    gp.GRB.ITERATION_LIMIT: "ITERATION_LIMIT",
    gp.GRB.NODE_LIMIT: "NODE_LIMIT",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.SOLUTION_LIMIT: "SOLUTION_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
    gp.GRB.NUMERIC: "NUMERIC",
    gp.GRB.SUBOPTIMAL: "SUBOPTIMAL",
    gp.GRB.INPROGRESS: "INPROGRESS",
    gp.GRB.USER_OBJ_LIMIT: "USER_OBJ_LIMIT",
}

result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": None,
    "projected_action": [],
    "max_constraint_violation": None,
    "integrality_violation": None,
}

if model.SolCount > 0:
    values = [variable.X for variable in x]
    projected_action = [int(round(value)) for value in values]
    violations = []
    for name, sense, rhs, terms in constraint_data:
        lhs = sum(coefficient * values[index] for index, coefficient in terms.items())
        if sense == "<=":
            violation = max(0.0, lhs - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs)
        else:
            violation = abs(lhs - rhs)
        violations.append(violation)
    objective_value = float(model.ObjVal)
    result["objective"] = objective_value if math.isfinite(objective_value) else None
    result["projected_action"] = projected_action
    result["max_constraint_violation"] = max(violations) if violations else 0.0
    result["integrality_violation"] = max(abs(value - round(value)) for value in values)

print(json.dumps(result, ensure_ascii=False))