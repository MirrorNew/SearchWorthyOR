import gurobipy as gp
import json

model = gp.Model("SWOR062")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

benefits = [1016, 955, 894, 852, 791, 749, 688, 646]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

# BASE CONSTRAINTS
model.addConstr(gp.quicksum(x) <= 3, name="maximum_enabled_units")
model.addConstr(x[0] + 2*x[1] + 3*x[2] + 4*x[3] + x[4] + 2*x[5] + 3*x[6] + 4*x[7] <= 6, name="grid_resource_capacity")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="minimum_clean_capability")
model.addConstr(x[1] + x[4] + x[7] >= 1, name="minimum_backup_capability")
model.addConstr(x[0] + x[3] >= 1, name="core_or_backup_pair")

# EVIDENCE PATCH 1: DOC-1C555C56EC8952B3, SQG excludes option A's VSQG path
model.addConstr(x[0] == 0, name="sqg_excludes_vsqg_simplified_path")

# EVIDENCE PATCH 2: DOC-1C555C56EC8952B3, actual-category-consistent capability
model.addConstr(x[1] + x[6] + x[7] >= 1, name="actual_category_consistent_capability")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
has_solution = model.SolCount > 0
values = [float(v.X) for v in x] if has_solution else [0.0] * 8
projected_action = [int(v >= 0.5) for v in values]

checks = [
    ([1,1,1,1,1,1,1,1], "<=", 3),
    ([1,2,3,4,1,2,3,4], "<=", 6),
    ([1,0,0,1,0,0,1,0], ">=", 1),
    ([0,1,0,0,1,0,0,1], ">=", 1),
    ([1,0,0,1,0,0,0,0], ">=", 1),
    ([1,0,0,0,0,0,0,0], "==", 0),
    ([0,1,0,0,0,0,1,1], ">=", 1)
]
violations = []
for coefficients, sense, rhs in checks:
    lhs = sum(coefficients[i] * values[i] for i in range(8))
    if sense == "<=":
        violations.append(max(0.0, lhs - rhs))
    elif sense == ">=":
        violations.append(max(0.0, rhs - lhs))
    else:
        violations.append(abs(lhs - rhs))

result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": float(model.ObjVal) if has_solution else None,
    "projected_action": projected_action,
    "max_constraint_violation": max(violations),
    "integrality_violation": max(abs(v - round(v)) for v in values)
}
print(json.dumps(result, ensure_ascii=False))
