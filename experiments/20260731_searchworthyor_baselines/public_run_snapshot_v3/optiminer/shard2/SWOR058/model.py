import gurobipy as gp
import json
import math

model = gp.Model("SWOR058_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

values = [1001, 959, 898, 856, 795, 753]
model.setObjective(gp.quicksum(values[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

constraint_data = [
    ({0: 1, 3: 1}, "==", 1, "chain_1_exactly_one"),
    ({1: 1, 4: 1}, "==", 1, "chain_2_exactly_one"),
    ({2: 1, 5: 1}, "==", 1, "chain_3_exactly_one"),
    ({1: 1, 4: 1, 5: 1}, "==", 1, "core_backup_emergency_exactly_one"),
    ({1: 1}, "==", 0, "regulatory_rest_eligibility_B")
]

for coefficients, sense, rhs, name in constraint_data:
    expression = gp.quicksum(coefficient * x[index] for index, coefficient in coefficients.items())
    if sense == "==":
        model.addConstr(expression == rhs, name=name)
    elif sense == "<=":
        model.addConstr(expression <= rhs, name=name)
    else:
        model.addConstr(expression >= rhs, name=name)

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
    solution_values = [variable.X for variable in x]
    projected_action = [int(round(value)) for value in solution_values]
    violations = []
    for coefficients, sense, rhs, name in constraint_data:
        lhs = sum(coefficient * solution_values[index] for index, coefficient in coefficients.items())
        if sense == "==":
            violation = abs(lhs - rhs)
        elif sense == "<=":
            violation = max(0.0, lhs - rhs)
        else:
            violation = max(0.0, rhs - lhs)
        violations.append(violation)
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in solution_values)
    objective = model.ObjVal
else:
    objective = None
    projected_action = [0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
