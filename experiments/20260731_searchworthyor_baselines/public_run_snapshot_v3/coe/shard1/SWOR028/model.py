import gurobipy as gp
import json
import math

model = gp.Model("SWOR028_patched")
model.Params.OutputFlag = 0

benefit = [1013, 952, 910, 849, 788, 746, 685, 643]
resource = [4, 1, 2, 3, 4, 1, 2, 3]
x = model.addVars(8, vtype=gp.GRB.BINARY, lb=0, ub=1, name="x")

model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

constraint_specs = [
    ("base_exactly_three_nodes", "==", 3.0, {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0, 7: 1.0}),
    ("base_service_area_1", ">=", 1.0, {0: 1.0, 2: 1.0, 4: 1.0, 6: 1.0}),
    ("base_service_area_2", ">=", 1.0, {1: 1.0, 3: 1.0, 5: 1.0, 7: 1.0}),
    ("base_G_H_mutual_exclusion", "<=", 1.0, {6: 1.0, 7: 1.0}),
    ("policy_at_least_one_guarantee_node", ">=", 1.0, {6: 1.0, 7: 1.0})
]

for name, sense, rhs, terms in constraint_specs:
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
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(x[i].X) for i in range(8)]
    projected_action = [int(round(value)) for value in values]
    violations = []
    for name, sense, rhs, terms in constraint_specs:
        lhs = sum(coef * values[index] for index, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal)
else:
    projected_action = []
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
