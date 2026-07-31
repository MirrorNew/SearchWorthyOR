import gurobipy as gp
import json

# CODE_REGION_VARIABLES
model = gp.Model("SWOR092_patched")
model.Params.OutputFlag = 0
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

# CODE_REGION_OBJECTIVE
utilities = [1000, 958, 897, 855, 794, 752, 691]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# CODE_REGION_BASE_CONSTRAINTS
model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="cover_period_1")
model.addConstr(x[1] + x[4] >= 1, name="cover_period_2")
model.addConstr(x[2] + x[5] >= 1, name="cover_period_3")
model.addConstr(x[1] + x[4] + x[6] == 1, name="exclusive_B_E_G")

# CODE_REGION_EXTERNAL_REST_PERIOD
model.addConstr(x[5] + x[6] >= 1, name="rest_period_4h")

# CODE_REGION_SOLVE_AND_REPORT
model.optimize()

if model.Status == gp.GRB.OPTIMAL:
    status = "OPTIMAL"
elif model.Status == gp.GRB.INFEASIBLE:
    status = "INFEASIBLE"
elif model.Status == gp.GRB.UNBOUNDED:
    status = "UNBOUNDED"
elif model.Status == gp.GRB.INF_OR_UNBD:
    status = "INF_OR_UNBD"
else:
    status = str(model.Status)

if model.SolCount > 0:
    values = [x[i].X for i in range(7)]
    projected_action = [int(round(value)) for value in values]
    rows = [
        (sum(values), "==", 3),
        (values[0] + values[3] + values[6], ">=", 1),
        (values[1] + values[4], ">=", 1),
        (values[2] + values[5], ">=", 1),
        (values[1] + values[4] + values[6], "==", 1),
        (values[5] + values[6], ">=", 1)
    ]
    violations = []
    for lhs, sense, rhs in rows:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    bound_violations = [max(0.0, -value, value - 1.0) for value in values]
    max_constraint_violation = max(violations + bound_violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
else:
    objective = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))