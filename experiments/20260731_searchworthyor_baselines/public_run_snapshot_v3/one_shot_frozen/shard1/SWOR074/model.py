import gurobipy as gp
import json
import math

model = gp.Model("SWOR074_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}
model.update()

objective_terms = {"x_0": 1014, "x_1": 953, "x_2": 911, "x_3": 850, "x_4": 789, "x_5": 747}
model.setObjective(gp.quicksum(coef * x[name] for name, coef in objective_terms.items()), gp.GRB.MAXIMIZE)

constraint_data = [
    ("unit_limit", "<=", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}),
    ("grid_capacity", "<=", 7, {"x_0": 4, "x_1": 1, "x_2": 2, "x_3": 3, "x_4": 4, "x_5": 1}),
    ("clean_capability", ">=", 1, {"x_0": 1, "x_3": 1}),
    ("backup_capability", ">=", 1, {"x_1": 1, "x_4": 1}),
    ("exclusive_core_backup_emergency", "==", 1, {"x_1": 1, "x_4": 1, "x_5": 1}),
    ("ldr_untreated_land_disposal", "<=", 1, {"x_0": 1, "x_1": 1, "x_4": -1, "x_5": -1})
]

for constraint_name, sense, rhs, terms in constraint_data:
    lhs = gp.quicksum(coef * x[name] for name, coef in terms.items())
    if sense == "<=":
        model.addConstr(lhs <= rhs, name=constraint_name)
    elif sense == ">=":
        model.addConstr(lhs >= rhs, name=constraint_name)
    else:
        model.addConstr(lhs == rhs, name=constraint_name)

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
    raw_values = {name: float(x[name].X) for name in names}
    projected_action = [int(round(raw_values[name])) for name in names]
    max_constraint_violation = 0.0
    for _, sense, rhs, terms in constraint_data:
        lhs_value = sum(coef * raw_values[name] for name, coef in terms.items())
        if sense == "<=":
            violation = max(0.0, lhs_value - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs_value)
        else:
            violation = math.fabs(lhs_value - rhs)
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(min(math.fabs(value), math.fabs(value - 1.0)) for value in raw_values.values())
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": max_constraint_violation,
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))