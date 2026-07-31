import gurobipy as gp
import json
import math

model = gp.Model("SWOR077_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
utilities = [1004, 962, 901, 859, 798, 737, 695, 634]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="required_selected_count")
model.addConstr(x[0] + x[1] >= 1, name="emergency_coverage")
model.addConstr(x[1] + x[2] >= 1, name="continuity_coverage")
model.addConstr(x[0] + x[2] >= 1, name="specialty_coverage")
model.addConstr(x[1] + x[4] + x[7] == 1, name="exclusive_choice_B_E_H")
model.addConstr(x[0] <= 0, name="policy_A_ineligible")

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
    values = [x[i].X for i in range(8)]
    projected_action = [int(round(v)) for v in values]
    lhs_checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[1], ">=", 1.0),
        (values[1] + values[2], ">=", 1.0),
        (values[0] + values[2], ">=", 1.0),
        (values[1] + values[4] + values[7], "==", 1.0),
        (values[0], "<=", 0.0)
    ]
    violations = []
    for lhs, sense, rhs in lhs_checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(v - round(v)) for v in values)
    objective = model.ObjVal
else:
    objective = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))
