import gurobipy as gp
import json
import math

model = gp.Model("SWOR006_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
revenues = [1018, 957, 896, 854, 793, 751]
model.setObjective(gp.quicksum(revenues[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="exactly_three_facilities")
model.addConstr(x[0] + x[2] + x[4] >= 1, name="service_area_1_coverage")
model.addConstr(x[1] + x[3] + x[5] >= 1, name="service_area_2_coverage")
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_alternative_D")
model.addConstr(x[0] == 0, name="section30c_registered_action_eligibility_A")

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
    constraint_data = [
        ("==", 3.0, [1, 1, 1, 1, 1, 1]),
        (">=", 1.0, [1, 0, 1, 0, 1, 0]),
        (">=", 1.0, [0, 1, 0, 1, 0, 1]),
        (">=", 1.0, [1, 0, 0, 1, 0, 0]),
        ("==", 0.0, [1, 0, 0, 0, 0, 0])
    ]
    violations = []
    for sense, rhs, coefficients in constraint_data:
        lhs = sum(coefficients[i] * values[i] for i in range(6))
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
else:
    projected_action = None
    max_constraint_violation = None
    integrality_violation = None
    objective = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))