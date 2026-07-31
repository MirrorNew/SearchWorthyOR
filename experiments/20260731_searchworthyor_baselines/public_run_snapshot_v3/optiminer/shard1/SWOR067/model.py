import gurobipy as gp
import json

model = gp.Model("SWOR067_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
utilities = [1002, 960, 899, 857, 796, 735]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]

model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="required_block_count")
model.addConstr(x[0] + x[1] >= 1, name="emergency_coverage")
model.addConstr(x[1] + x[2] >= 1, name="continuity_coverage")
model.addConstr(x[0] + x[2] >= 1, name="specialty_coverage")
model.addConstr(x[0] + x[1] <= 1, name="policy_A_branch_excludes_B")

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
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    objective = model.ObjVal
    checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[1], ">=", 1.0),
        (values[1] + values[2], ">=", 1.0),
        (values[0] + values[2], ">=", 1.0),
        (values[0] + values[1], "<=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    projected_action = [0, 0, 0, 0, 0, 0]
    objective = None
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