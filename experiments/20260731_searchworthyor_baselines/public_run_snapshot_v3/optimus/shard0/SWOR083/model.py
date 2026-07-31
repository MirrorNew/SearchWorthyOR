import gurobipy as gp
import json

model = gp.Model("SWOR083_patched")
model.Params.OutputFlag = 0

# CODE_REGION: variable_domains
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

# CODE_REGION: objective
profits = [1012, 951, 909, 848, 806, 745, 684]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# CODE_REGION: base_required_shift_count
model.addConstr(gp.quicksum(x) == 3, name="required_shift_count")

# CODE_REGION: base_time_period_1_coverage
model.addConstr(x[0] + x[3] + x[6] >= 1, name="time_period_1_coverage")

# CODE_REGION: base_time_period_2_coverage
model.addConstr(x[1] + x[4] >= 1, name="time_period_2_coverage")

# CODE_REGION: base_time_period_3_coverage
model.addConstr(x[2] + x[5] >= 1, name="time_period_3_coverage")

# CODE_REGION: base_core_candidate
model.addConstr(x[0] + x[3] >= 1, name="core_candidate_A_or_D")

# CODE_REGION: evidence_DOC_A4922229EA1563A2
model.addConstr(x[0] + x[1] <= 1, name="policy_conflict_A_B")

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
    values = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in values]
    lhs_checks = [
        ("==", sum(values), 3.0),
        (">=", values[0] + values[3] + values[6], 1.0),
        (">=", values[1] + values[4], 1.0),
        (">=", values[2] + values[5], 1.0),
        (">=", values[0] + values[3], 1.0),
        ("<=", values[0] + values[1], 1.0)
    ]
    violations = []
    for sense, lhs, rhs in lhs_checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in values)
    objective = float(model.ObjVal)
else:
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
