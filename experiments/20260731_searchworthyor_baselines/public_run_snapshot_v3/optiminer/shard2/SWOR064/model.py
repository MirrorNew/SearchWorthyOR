import gurobipy as gp
import json
import math

m = gp.Model("SWOR064_patched")
m.Params.OutputFlag = 0

# VARIABLES_PUBLIC_TASK
x = [m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

# OBJECTIVE_PUBLIC_TASK
benefit = [1001, 959, 898, 856, 795, 753, 692, 631]
m.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

# BASE_CONSTRAINT_FACILITY_COUNT
m.addConstr(gp.quicksum(x) == 3, name="facility_count_exactly_3")

# BASE_CONSTRAINT_SERVICE_AREA_1
m.addConstr(x[0] + x[2] + x[4] + x[6] >= 1, name="service_area_1_coverage")

# BASE_CONSTRAINT_SERVICE_AREA_2
m.addConstr(x[1] + x[3] + x[5] + x[7] >= 1, name="service_area_2_coverage")

# BASE_CONSTRAINT_CORE_CANDIDATES
m.addConstr(x[0] + x[1] + x[2] >= 2, name="core_candidates_at_least_2")

# POLICY_DOC_94E650D2DA55246D
m.addConstr(x[0] + x[1] <= 1, name="policy_A_B_mutual_exclusion")

# NO_RESOURCE_OR_CATEGORY_CONSTRAINT: no aggregate resource limit or category trigger was supplied.
m.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(m.Status, str(m.Status))

if m.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(round(value)) for value in values]

    checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[2] + values[4] + values[6], ">=", 1.0),
        (values[1] + values[3] + values[5] + values[7], ">=", 1.0),
        (values[0] + values[1] + values[2], ">=", 2.0),
        (values[0] + values[1], "<=", 1.0)
    ]

    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(rhs - lhs, 0.0))
        else:
            violations.append(max(lhs - rhs, 0.0))

    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(m.ObjVal) if math.isfinite(m.ObjVal) else None
else:
    objective = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

# SOLVE_AND_REPORT
result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
