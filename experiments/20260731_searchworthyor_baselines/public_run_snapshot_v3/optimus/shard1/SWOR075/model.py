import gurobipy as gp
import json
import math

model = gp.Model("SWOR075_patched")
model.Params.OutputFlag = 0

# [VARS] Binary node-selection variables in action_projection order A..G.
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}") for i in range(7)]

# [OBJ] Maximize total network coverage benefit.
benefits = [1015, 954, 912, 851, 790, 748, 687]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# [C_SELECT] Exactly three nodes must be selected.
model.addConstr(gp.quicksum(x[i] for i in range(7)) == 3, name="select_exactly_3")

# [C_COVER_1] Service area 1 coverage.
model.addConstr(x[0] + x[2] + x[4] + x[6] >= 1, name="cover_service_area_1")

# [C_COVER_2] Service area 2 coverage.
model.addConstr(x[1] + x[3] + x[5] >= 1, name="cover_service_area_2")

# [C_POLICY_A] DOC-FBDDC4AE130DB3C9 makes node A ineligible.
model.addConstr(x[0] == 0, name="node_A_ineligible")

model.optimize()

# [SOLVE_OUTPUT] Project and independently check the returned solution.
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
    objective = float(model.ObjVal)

    rows = [
        ([1, 1, 1, 1, 1, 1, 1], "==", 3.0),
        ([1, 0, 1, 0, 1, 0, 1], ">=", 1.0),
        ([0, 1, 0, 1, 0, 1, 0], ">=", 1.0),
        ([1, 0, 0, 0, 0, 0, 0], "==", 0.0)
    ]
    violations = []
    for coefficients, sense, rhs in rows:
        lhs = sum(coefficients[i] * values[i] for i in range(7))
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
    projected_action = None
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
