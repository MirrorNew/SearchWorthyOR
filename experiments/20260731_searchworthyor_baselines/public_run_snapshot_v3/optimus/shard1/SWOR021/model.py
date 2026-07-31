import gurobipy as gp
import json
import math

model = gp.Model("SWOR021_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

revenues = [1018, 957, 896, 854, 793, 751, 690]
resources = [2, 3, 4, 1, 2, 3, 4]
model.setObjective(gp.quicksum(revenues[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) <= 3, name="maximum_selected_plans")
model.addConstr(gp.quicksum(resources[i] * x[i] for i in range(7)) <= 9, name="grid_resource_capacity")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="minimum_clean_capability")
model.addConstr(x[1] + x[4] >= 1, name="minimum_reserve_capability")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="minimum_core_candidates")
model.addConstr(x[0] == 0, name="regulatory_ineligibility_plan_A")

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
    values = [float(v.X) for v in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)
else:
    values = [0.0] * 7
    projected_action = [0] * 7
    objective = None

lhs_values = [
    sum(values),
    sum(resources[i] * values[i] for i in range(7)),
    values[0] + values[3] + values[6],
    values[1] + values[4],
    values[0] + values[1] + values[2],
    values[0]
]
constraint_specs = [
    ("<=", 3.0),
    ("<=", 9.0),
    (">=", 1.0),
    (">=", 1.0),
    (">=", 2.0),
    ("==", 0.0)
]
violations = []
for lhs, spec in zip(lhs_values, constraint_specs):
    sense, rhs = spec
    if sense == "<=":
        violations.append(max(0.0, lhs - rhs))
    elif sense == ">=":
        violations.append(max(0.0, rhs - lhs))
    else:
        violations.append(abs(lhs - rhs))

bound_violations = [max(0.0, -value, value - 1.0) for value in values]
max_constraint_violation = max(violations + bound_violations)
integrality_violation = max(abs(value - round(value)) for value in values)

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": float(max_constraint_violation),
    "integrality_violation": float(integrality_violation)
}
print(json.dumps(result, ensure_ascii=False))
