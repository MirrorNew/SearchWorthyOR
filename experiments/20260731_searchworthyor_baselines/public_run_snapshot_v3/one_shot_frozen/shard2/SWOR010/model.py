import gurobipy as gp
import json
import math

m = gp.Model("SWOR010_patched")
m.Params.OutputFlag = 0

x = [
    m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_0"),
    m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_1"),
    m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_2"),
    m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_3"),
    m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_4"),
    m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_5")
]

profits = [1000, 958, 897, 855, 794, 752]
m.setObjective(gp.quicksum(profits[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

m.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
m.addConstr(x[0] + x[1] + x[3] >= 1, name="front_arrival_min1")
m.addConstr(x[1] + x[2] + x[4] >= 1, name="back_arrival_min1")
m.addConstr(x[0] + x[1] + x[2] >= 2, name="core_first3_min2")
m.addConstr(x[0] + x[1] <= 1, name="policy_A_excludes_B")

m.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(m.Status, str(m.Status))

if m.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [1 if value >= 0.5 else 0 for value in values]
    objective = float(m.ObjVal)

    checks = [
        ("==", 3.0, sum(values)),
        (">=", 1.0, values[0] + values[1] + values[3]),
        (">=", 1.0, values[1] + values[2] + values[4]),
        (">=", 2.0, values[0] + values[1] + values[2]),
        ("<=", 1.0, values[0] + values[1])
    ]
    violations = []
    for sense, rhs, lhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))

    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    objective = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))