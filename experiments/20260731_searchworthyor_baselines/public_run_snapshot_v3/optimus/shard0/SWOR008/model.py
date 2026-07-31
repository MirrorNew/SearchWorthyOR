import gurobipy
import json
import math

model = gurobipy.Model("SWOR008_patched")
model.Params.OutputFlag = 0

x = [
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}")
    for i in range(7)
]

benefit = [1016, 955, 894, 852, 791, 749, 688]
model.setObjective(
    gurobipy.quicksum(benefit[i] * x[i] for i in range(7)),
    gurobipy.GRB.MAXIMIZE,
)

model.addConstr(
    gurobipy.quicksum(x[i] for i in range(7)) == 3,
    name="required_node_count",
)
model.addConstr(
    x[0] + x[2] + x[4] + x[6] >= 1,
    name="service_area_1_min_coverage",
)
model.addConstr(
    x[1] + x[3] + x[5] >= 1,
    name="service_area_2_min_coverage",
)
model.addConstr(
    x[1] + x[4] + x[6] == 1,
    name="exclusive_choice_B_E_G",
)

# REGION existing_vehicle_disposal_conflict_A_B
model.addConstr(
    x[0] + x[1] <= 1,
    name="existing_vehicle_disposal_conflict_A_B",
)
# END REGION existing_vehicle_disposal_conflict_A_B

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
    gurobipy.GRB.INTERRUPTED: "INTERRUPTED",
}
status = status_names.get(model.Status, str(model.Status))

result = {
    "status": status,
    "objective": None,
    "projected_action": None,
    "max_constraint_violation": None,
    "integrality_violation": None,
}

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected_action = [int(value >= 0.5) for value in values]

    checks = [
        ({0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1}, "==", 3.0),
        ({0: 1, 2: 1, 4: 1, 6: 1}, ">=", 1.0),
        ({1: 1, 3: 1, 5: 1}, ">=", 1.0),
        ({1: 1, 4: 1, 6: 1}, "==", 1.0),
        ({0: 1, 1: 1}, "<=", 1.0),
    ]

    violations = []
    for terms, sense, rhs in checks:
        lhs = sum(coef * values[index] for index, coef in terms.items())
        if sense == "<=":
            violation = max(0.0, lhs - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs)
        else:
            violation = abs(lhs - rhs)
        violations.append(violation)

    objective = float(model.ObjVal)
    result = {
        "status": status,
        "objective": objective if math.isfinite(objective) else None,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(value - round(value)) for value in values),
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))
