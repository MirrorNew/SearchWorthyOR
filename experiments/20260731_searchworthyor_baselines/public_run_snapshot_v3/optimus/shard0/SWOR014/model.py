import gurobipy as gp
import json
import math

# REGION VARIABLES
model = gp.Model("SWOR014_patched")
model.Params.OutputFlag = 0
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

# REGION OBJECTIVE
benefits = [1010, 949, 907, 846, 804, 743, 682, 640]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

# REGION BASE_CONSTRAINTS
base_constraints = [
    ("select_exactly_3", "==", 3, {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1}),
    ("cover_period_1", ">=", 1, {0: 1, 3: 1, 6: 1}),
    ("cover_period_2", ">=", 1, {1: 1, 4: 1, 7: 1}),
    ("cover_period_3", ">=", 1, {2: 1, 5: 1}),
    ("select_exactly_one_B_E_H", "==", 1, {1: 1, 4: 1, 7: 1})
]

# REGION EXTERNAL_POLICY
policy_constraints = [
    ("external_A_ineligible", "==", 0, {0: 1})
]

constraints_data = base_constraints + policy_constraints
for name, sense, rhs, terms in constraints_data:
    lhs = gp.quicksum(coef * x[index] for index, coef in terms.items())
    if sense == "==":
        model.addConstr(lhs == rhs, name=name)
    elif sense == ">=":
        model.addConstr(lhs >= rhs, name=name)
    else:
        model.addConstr(lhs <= rhs, name=name)

# REGION SOLVE_AND_REPORT
model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    violations = []
    for value in values:
        violations.append(max(0.0, -value))
        violations.append(max(0.0, value - 1.0))
    for name, sense, rhs, terms in constraints_data:
        lhs_value = sum(coef * values[index] for index, coef in terms.items())
        if sense == "==":
            violations.append(abs(lhs_value - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs_value))
        else:
            violations.append(max(0.0, lhs_value - rhs))
    integrality_violation = max(abs(value - round(value)) for value in values)
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": float(max(violations)),
        "integrality_violation": float(integrality_violation)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0 for _ in x],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))