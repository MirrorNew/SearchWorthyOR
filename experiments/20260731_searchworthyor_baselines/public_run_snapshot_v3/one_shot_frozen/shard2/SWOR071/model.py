import gurobipy as gp
import json
import math

model = gp.Model("SWOR071_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

objective_coefficients = [1006, 964, 903, 842, 800, 739, 697]
model.setObjective(
    gp.quicksum(objective_coefficients[i] * x[i] for i in range(7)),
    gp.GRB.MAXIMIZE,
)

model.addConstr(gp.quicksum(x) == 3, name="activate_exactly_3")
model.addConstr(x[0] + x[1] >= 1, name="emergency_A_or_B")
model.addConstr(x[1] + x[2] >= 1, name="continuity_B_or_C")
model.addConstr(x[0] + x[2] >= 1, name="specialty_A_or_C")
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_backup_D")
model.addConstr(x[0] + x[1] <= 1, name="policy_A_branch_excludes_B")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [v.X for v in x]
    projected_action = [int(round(value)) for value in values]
    integrality_violation = max(abs(value - round(value)) for value in values)

    constraint_specs = [
        ({0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1}, "==", 3),
        ({0: 1, 1: 1}, ">=", 1),
        ({1: 1, 2: 1}, ">=", 1),
        ({0: 1, 2: 1}, ">=", 1),
        ({0: 1, 3: 1}, ">=", 1),
        ({0: 1, 1: 1}, "<=", 1),
    ]
    violations = []
    for coefficients, sense, rhs in constraint_specs:
        lhs = sum(coefficient * values[index] for index, coefficient in coefficients.items())
        if sense == "==":
            violation = abs(lhs - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs)
        else:
            violation = max(0.0, lhs - rhs)
        violations.append(violation)

    objective = float(model.ObjVal)
    if not math.isfinite(objective):
        objective = None
    result = {
        "status": status,
        "objective": objective,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": integrality_violation,
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None,
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))