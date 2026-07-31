import gurobipy as gp
import json
import math

model = gp.Model("SWOR062_patched")
model.Params.OutputFlag = 0

benefits = [1016, 955, 894, 852, 791, 749, 688, 646]
resources = [1, 2, 3, 4, 1, 2, 3, 4]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

constraint_specs = [
    ("max_energy_units", "<=", 3, {i: 1 for i in range(8)}),
    ("grid_resource_capacity", "<=", 6, {i: resources[i] for i in range(8)}),
    ("minimum_clean_capability", ">=", 1, {0: 1, 3: 1, 6: 1}),
    ("minimum_backup_capability", ">=", 1, {1: 1, 4: 1, 7: 1}),
    ("core_A_or_backup_D", ">=", 1, {0: 1, 3: 1}),
    ("rcra_sqg_excludes_vsqg_A", "==", 0, {0: 1})
]

for name, sense, rhs, terms in constraint_specs:
    expr = gp.quicksum(coef * x[i] for i, coef in terms.items())
    if sense == "<=":
        model.addConstr(expr <= rhs, name=name)
    elif sense == ">=":
        model.addConstr(expr >= rhs, name=name)
    else:
        model.addConstr(expr == rhs, name=name)

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
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    max_constraint_violation = 0.0
    for name, sense, rhs, terms in constraint_specs:
        lhs = sum(coef * values[i] for i, coef in terms.items())
        if sense == "<=":
            violation = max(0.0, lhs - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs)
        else:
            violation = abs(lhs - rhs)
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
else:
    projected_action = []
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