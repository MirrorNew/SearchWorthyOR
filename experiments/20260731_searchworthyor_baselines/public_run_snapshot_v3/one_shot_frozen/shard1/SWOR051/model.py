import gurobipy as gp
import json
import math

model = gp.Model("SWOR051_patched")
model.Params.OutputFlag = 0

# REGION_VARIABLES
names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}
model.update()

# REGION_OBJECTIVE
objective_terms = {"x_0": 1004, "x_1": 962, "x_2": 901, "x_3": 859, "x_4": 798, "x_5": 737}
model.setObjective(gp.quicksum(coef * x[name] for name, coef in objective_terms.items()), gp.GRB.MAXIMIZE)

rows = [
    # REGION_BASE_MAX_MODULES
    ("max_modules", "<=", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}),
    # REGION_BASE_ZONE_1
    ("zone_1_connectivity", ">=", 1, {"x_0": 1, "x_3": 1}),
    # REGION_BASE_ZONE_2
    ("zone_2_connectivity", ">=", 1, {"x_1": 1, "x_4": 1}),
    # REGION_BASE_ZONE_3
    ("zone_3_connectivity", ">=", 1, {"x_2": 1, "x_5": 1}),
    # REGION_BASE_A_BACKHAUL
    ("a_requires_b_or_e", ">=", 0, {"x_0": -1, "x_1": 1, "x_4": 1}),
    # REGION_BASE_CORE_A_OR_D
    ("core_a_or_d", ">=", 1, {"x_0": 1, "x_3": 1}),
    # REGION_POLICY_AB_MUTEX
    ("policy_ab_mutex", "<=", 1, {"x_0": 1, "x_1": 1})
]

for row_name, row_sense, rhs, terms in rows:
    lhs = gp.quicksum(coef * x[name] for name, coef in terms.items())
    if row_sense == "<=":
        model.addConstr(lhs <= rhs, name=row_name)
    elif row_sense == ">=":
        model.addConstr(lhs >= rhs, name=row_name)
    else:
        model.addConstr(lhs == rhs, name=row_name)

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
    values = {name: float(x[name].X) for name in names}
    projected_action = [int(round(values[name])) for name in names]
    objective = float(model.ObjVal)
    violations = []
    for row_name, row_sense, rhs, terms in rows:
        lhs_value = sum(coef * values[name] for name, coef in terms.items())
        if row_sense == "<=":
            violations.append(max(0.0, lhs_value - rhs))
        elif row_sense == ">=":
            violations.append(max(0.0, rhs - lhs_value))
        else:
            violations.append(abs(lhs_value - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(values[name] - round(values[name])) for name in names)
else:
    objective = None
    projected_action = [0 for _ in names]
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
