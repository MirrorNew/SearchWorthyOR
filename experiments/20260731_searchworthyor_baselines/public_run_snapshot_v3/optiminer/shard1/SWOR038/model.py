import gurobipy as gp
import json
import math

model = gp.Model("SWOR038_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
model.setObjective(
    1011 * x[0] + 950 * x[1] + 908 * x[2] +
    847 * x[3] + 805 * x[4] + 744 * x[5],
    gp.GRB.MAXIMIZE
)

constraint_data = [
    ("module_limit", "<=", 3.0, {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0}),
    ("zone_1_coverage", ">=", 1.0, {0: 1.0, 3: 1.0}),
    ("zone_2_coverage", ">=", 1.0, {1: 1.0, 4: 1.0}),
    ("zone_3_coverage", ">=", 1.0, {2: 1.0, 5: 1.0}),
    ("a_backhaul", "<=", 0.0, {0: 1.0, 1: -1.0, 4: -1.0}),
    ("exactly_one_b_e_f", "==", 1.0, {1: 1.0, 4: 1.0, 5: 1.0}),
    ("meal_period_compliance_a", "<=", 0.0, {0: 1.0, 4: -1.0, 5: -1.0})
]

for name, sense, rhs, terms in constraint_data:
    lhs = gp.quicksum(coef * x[index] for index, coef in terms.items())
    if sense == "<=":
        model.addConstr(lhs <= rhs, name=name)
    elif sense == ">=":
        model.addConstr(lhs >= rhs, name=name)
    else:
        model.addConstr(lhs == rhs, name=name)

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw_values = [variable.X for variable in x]
    projected_action = [int(round(value)) for value in raw_values]
    violations = []
    for name, sense, rhs, terms in constraint_data:
        lhs = sum(coef * raw_values[index] for index, coef in terms.items())
        if sense == "<=":
            violation = max(0.0, lhs - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs)
        else:
            violation = abs(lhs - rhs)
        violations.append(violation)
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in raw_values)
    objective = float(model.ObjVal)
else:
    projected_action = [0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))