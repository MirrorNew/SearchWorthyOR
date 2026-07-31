import gurobipy as gp
import json
import math

model = gp.Model("SWOR069")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
model.setObjective(1017*x[0] + 956*x[1] + 895*x[2] + 853*x[3] + 792*x[4] + 750*x[5], gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="frozen_assignment_count")
model.addConstr(x[0] + x[3] <= 1, name="resource_subject_1_exclusivity")
model.addConstr(x[1] + x[4] <= 1, name="resource_subject_2_exclusivity")
model.addConstr(x[2] + x[5] <= 1, name="resource_subject_3_exclusivity")
model.addConstr(x[1] + x[4] + x[5] == 1, name="core_backup_emergency_exactly_one")

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
    values = [v.X for v in x]
    projected_action = [int(value >= 0.5) for value in values]
    lhs_values = [
        sum(values),
        values[0] + values[3],
        values[1] + values[4],
        values[2] + values[5],
        values[1] + values[4] + values[5]
    ]
    senses = ["==", "<=", "<=", "<=", "=="]
    rhs_values = [3.0, 1.0, 1.0, 1.0, 1.0]
    violations = []
    for lhs, sense, rhs in zip(lhs_values, senses, rhs_values):
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
else:
    projected_action = [0, 0, 0, 0, 0, 0]
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
print(json.dumps(result, ensure_ascii=False))