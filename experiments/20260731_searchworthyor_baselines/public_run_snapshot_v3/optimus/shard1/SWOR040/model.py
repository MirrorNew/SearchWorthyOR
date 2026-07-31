import gurobipy as gp
import json
import math

model = gp.Model("SWOR040")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

benefit = [1011, 950, 908, 847, 805, 744]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="required_node_count")
model.addConstr(x[0] + x[2] + x[4] >= 1, name="service_area_1_coverage")
model.addConstr(x[1] + x[3] + x[5] >= 1, name="service_area_2_coverage")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="minimum_core_nodes")
model.addConstr(x[0] + x[1] <= 1, name="policy_mutex_A_B")

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
    values = [v.X for v in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)
    constraint_specs = [
        ("==", [1, 1, 1, 1, 1, 1], 3),
        (">=", [1, 0, 1, 0, 1, 0], 1),
        (">=", [0, 1, 0, 1, 0, 1], 1),
        (">=", [1, 1, 1, 0, 0, 0], 2),
        ("<=", [1, 1, 0, 0, 0, 0], 1)
    ]
    violations = []
    for sense, coefficients, rhs in constraint_specs:
        lhs = sum(coefficients[i] * values[i] for i in range(6))
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
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
print(json.dumps(result, ensure_ascii=False))
