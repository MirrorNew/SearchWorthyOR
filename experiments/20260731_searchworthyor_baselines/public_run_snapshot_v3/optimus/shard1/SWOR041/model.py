import gurobipy as gp
import json
import math

model = gp.Model("SWOR041_patched")
model.Params.OutputFlag = 0

utilities = [1000, 958, 897, 855, 794, 752, 691]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

constraint_specs = []

def add_linear(name, terms, sense, rhs):
    expression = gp.quicksum(coefficient * x[index] for index, coefficient in terms.items())
    if sense == "==":
        model.addConstr(expression == rhs, name=name)
    elif sense == ">=":
        model.addConstr(expression >= rhs, name=name)
    elif sense == "<=":
        model.addConstr(expression <= rhs, name=name)
    constraint_specs.append((name, terms, sense, rhs))

add_linear("select_exactly_3", {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1}, "==", 3)
add_linear("emergency_coverage_A_B", {0: 1, 1: 1}, ">=", 1)
add_linear("continuity_coverage_B_C", {1: 1, 2: 1}, ">=", 1)
add_linear("specialty_coverage_A_C", {0: 1, 2: 1}, ">=", 1)
add_linear("backup_mutual_exclusion_F_G", {5: 1, 6: 1}, "<=", 1)
add_linear("eligibility_A", {0: 1}, "==", 0)

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
    values = [variable.X for variable in x]
    projected_action = [int(value >= 0.5) for value in values]
    objective = float(model.ObjVal)
    max_constraint_violation = 0.0
    for _, terms, sense, rhs in constraint_specs:
        lhs = sum(coefficient * values[index] for index, coefficient in terms.items())
        if sense == "==":
            violation = abs(lhs - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs)
        else:
            violation = max(0.0, lhs - rhs)
        max_constraint_violation = max(max_constraint_violation, violation)
    for value in values:
        max_constraint_violation = max(max_constraint_violation, max(0.0, -value), max(0.0, value - 1.0))
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0]
    objective = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))