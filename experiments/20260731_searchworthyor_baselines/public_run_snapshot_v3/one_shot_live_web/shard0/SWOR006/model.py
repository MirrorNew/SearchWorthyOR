import gurobipy as gp
import json
import math

model = gp.Model("SWOR006_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

objective_coefficients = [1018, 957, 896, 854, 793, 751]
model.setObjective(gp.quicksum(objective_coefficients[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="facility_count")
model.addConstr(x[0] + x[2] + x[4] >= 1, name="service_area_1_coverage")
model.addConstr(x[1] + x[3] + x[5] >= 1, name="service_area_2_coverage")
model.addConstr(x[0] + x[3] >= 1, name="core_or_backup")
model.addConstr(x[0] <= 0, name="section30c_location_eligibility_node_a")

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
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)

    checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[2] + values[4], ">=", 1.0),
        (values[1] + values[3] + values[5], ">=", 1.0),
        (values[0] + values[3], ">=", 1.0),
        (values[0], "<=", 0.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))

    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    objective = None
    projected_action = []
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