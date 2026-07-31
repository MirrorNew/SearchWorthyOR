import gurobipy as gp
import json
import math

model = gp.Model("SWOR005_patched")
model.Params.OutputFlag = 0

# REGION variables
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

# REGION objective
profits = [1003, 961, 900, 858, 797, 736, 694]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# REGION base_constraints
model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[2] + x[4] + x[6] >= 1, name="service_area_1_min_1")
model.addConstr(x[1] + x[3] + x[5] >= 1, name="service_area_2_min_1")
model.addConstr(x[5] + x[6] <= 1, name="terminal_backup_mutex")

# REGION evidence_patch_DOC_951549225889172D
model.addConstr(x[5] + x[6] >= 1, name="safeguard_option_min_1")

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
    values = [x[i].X for i in range(7)]
    projected_action = [int(round(v)) for v in values]
    integrality_violation = max(abs(v - round(v)) for v in values)
    checks = [
        (sum(values), "==", 3),
        (values[0] + values[2] + values[4] + values[6], ">=", 1),
        (values[1] + values[3] + values[5], ">=", 1),
        (values[5] + values[6], "<=", 1),
        (values[5] + values[6], ">=", 1)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
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

print(json.dumps(result, ensure_ascii=False))
