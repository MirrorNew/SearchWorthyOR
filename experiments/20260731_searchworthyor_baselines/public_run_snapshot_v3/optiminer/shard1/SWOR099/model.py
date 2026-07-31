import gurobipy as gp
import json

# REGION variables
model = gp.Model("SWOR099_patched")
model.Params.OutputFlag = 0
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

# REGION objective
utility = [1015, 954, 912, 851, 790, 748, 687, 645]
model.setObjective(gp.quicksum(utility[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

# REGION base_constraints
model.addConstr(gp.quicksum(x) == 3, name="select_exactly_three")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="front_segment_arrival")
model.addConstr(x[1] + x[2] + x[4] + x[7] >= 1, name="back_segment_arrival")
model.addConstr(x[1] + x[4] + x[7] == 1, name="core_exactly_one")

# REGION evidence_patch_DOC_A5F33889CED21786
model.addConstr(x[6] + x[7] >= 1, name="fruit_or_vegetable_required")

# REGION solve_and_projection
model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))
has_solution = model.SolCount > 0

if has_solution:
    values = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in values]
    objective = float(model.ObjVal)
    checks = [
        ("==", sum(values), 3.0),
        (">=", values[0] + values[1] + values[3] + values[6], 1.0),
        (">=", values[1] + values[2] + values[4] + values[7], 1.0),
        ("==", values[1] + values[4] + values[7], 1.0),
        (">=", values[6] + values[7], 1.0)
    ]
    violations = []
    for sense, lhs, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in values)
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
