import gurobipy as gp
import json

model = gp.Model("SWOR012")
model.Params.OutputFlag = 0
model.Params.Threads = 1
model.Params.Seed = 0
model.Params.PoolSearchMode = 2
model.Params.PoolSolutions = 64
model.Params.PoolGap = 0.0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
coeff = [1015, 954, 912, 851, 790, 748]
model.setObjective(gp.quicksum(coeff[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[1] >= 1, name="emergency_coverage")
model.addConstr(x[1] + x[2] >= 1, name="continuous_care_coverage")
model.addConstr(x[0] + x[2] >= 1, name="specialty_coverage")
model.addConstr(x[0] + x[3] >= 1, name="core_candidate_or_backup")
model.addConstr(x[0] - x[4] - x[5] <= 0, name="rcra_lqg_requires_90_day_path")
model.addConstr(x[0] + x[1] <= 1, name="rcra_lqg_excludes_180_day_path")

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
    optimal = []
    for solution_number in range(model.SolCount):
        model.Params.SolutionNumber = solution_number
        values = [x[i].Xn for i in range(6)]
        pool_objective = model.PoolObjVal
        if abs(pool_objective - model.ObjVal) <= 1e-6:
            bits = [int(round(value)) for value in values]
            optimal.append((bits, values))

    if optimal:
        projected_action, values = max(optimal, key=lambda item: item[0])
    else:
        values = [x[i].X for i in range(6)]
        projected_action = [int(round(value)) for value in values]

    lhs_checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[1], ">=", 1.0),
        (values[1] + values[2], ">=", 1.0),
        (values[0] + values[2], ">=", 1.0),
        (values[0] + values[3], ">=", 1.0),
        (values[0] - values[4] - values[5], "<=", 0.0),
        (values[0] + values[1], "<=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in lhs_checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))

    result = {
        "status": status,
        "objective": sum(coeff[i] * values[i] for i in range(6)),
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(value - round(value)) for value in values)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))