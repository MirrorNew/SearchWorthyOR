import gurobipy as gp
import json
import math

model = gp.Model("SWOR016_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
benefits = [1007, 965, 904, 843, 801, 740, 698, 637]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="build_exactly_three")
model.addConstr(x[0] + x[2] + x[4] + x[6] >= 1, name="service_area_1_coverage")
model.addConstr(x[1] + x[3] + x[5] + x[7] >= 1, name="service_area_2_coverage")
model.addConstr(x[1] + x[4] + x[7] == 1, name="core_backup_emergency_exactly_one")
model.addConstr(x[0] + x[1] <= 1, name="compliance_A_excludes_B")

constraint_specs = [
    ("==", 3.0, {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1}),
    (">=", 1.0, {0: 1, 2: 1, 4: 1, 6: 1}),
    (">=", 1.0, {1: 1, 3: 1, 5: 1, 7: 1}),
    ("==", 1.0, {1: 1, 4: 1, 7: 1}),
    ("<=", 1.0, {0: 1, 1: 1})
]

model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": None,
    "projected_action": [0] * 8,
    "max_constraint_violation": None,
    "integrality_violation": None
}

if model.SolCount > 0:
    values = [float(x[i].X) for i in range(8)]
    projected_action = [int(round(value)) for value in values]
    violations = []
    for sense, rhs, terms in constraint_specs:
        lhs = sum(coefficient * values[index] for index, coefficient in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    result["objective"] = float(model.ObjVal) if math.isfinite(model.ObjVal) else None
    result["projected_action"] = projected_action
    result["max_constraint_violation"] = max(violations) if violations else 0.0
    result["integrality_violation"] = max(abs(value - round(value)) for value in values)

print(json.dumps(result, ensure_ascii=False, sort_keys=True))