import gurobipy as gp
import json

# [model_data]
benefit = [1013, 952, 910, 849, 788, 746]
resource = [1, 2, 3, 4, 1, 2]
model = gp.Model("SWOR033")
model.Params.OutputFlag = 0
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

# [objective_block]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

# [base_constraint_block/max_selected]
model.addConstr(gp.quicksum(x) <= 3, name="max_selected")

# [base_constraint_block/resource_capacity]
model.addConstr(gp.quicksum(resource[i] * x[i] for i in range(6)) <= 6, name="resource_capacity")

# [base_constraint_block/minimum_clean]
model.addConstr(x[0] + x[3] >= 1, name="minimum_clean")

# [base_constraint_block/minimum_backup]
model.addConstr(x[1] + x[4] >= 1, name="minimum_backup")

# [policy_constraint_block/policy_A_excludes_B]
model.addConstr(x[0] + x[1] <= 1, name="policy_A_excludes_B")

# [solve_and_output]
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
    raw = [v.X for v in x]
    projected = [int(round(value)) for value in raw]
    integrality_violation = max(abs(value - round(value)) for value in raw)
    rows = [
        ({0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1}, "<=", 3),
        ({0: 1, 1: 2, 2: 3, 3: 4, 4: 1, 5: 2}, "<=", 6),
        ({0: 1, 3: 1}, ">=", 1),
        ({1: 1, 4: 1}, ">=", 1),
        ({0: 1, 1: 1}, "<=", 1)
    ]
    violations = []
    for coefficients, row_sense, rhs in rows:
        lhs = sum(coefficient * raw[index] for index, coefficient in coefficients.items())
        if row_sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif row_sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected,
        "max_constraint_violation": max(violations),
        "integrality_violation": integrality_violation
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
