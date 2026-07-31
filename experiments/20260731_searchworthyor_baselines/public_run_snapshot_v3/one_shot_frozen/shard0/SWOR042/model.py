import gurobipy as gp
import json
import math

m = gp.Model("SWOR042_patched")
m.Params.OutputFlag = 0

x = [m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

objective_coefficients = [1002, 960, 899, 857, 796, 735]
m.setObjective(gp.quicksum(objective_coefficients[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

constraints_data = [
    ("select_exactly_three", "==", 3.0, {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0}),
    ("period_1_coverage", ">=", 1.0, {0: 1.0, 3: 1.0}),
    ("period_2_coverage", ">=", 1.0, {1: 1.0, 4: 1.0}),
    ("period_3_coverage", ">=", 1.0, {2: 1.0, 5: 1.0}),
    ("core_A_or_backup_D", ">=", 1.0, {0: 1.0, 3: 1.0}),
    ("meal_standby_incompatibility", "<=", 1.0, {0: 1.0, 1: 1.0})
]

for name, sense, rhs, terms in constraints_data:
    lhs = gp.quicksum(coef * x[index] for index, coef in terms.items())
    if sense == "<=":
        m.addConstr(lhs <= rhs, name=name)
    elif sense == ">=":
        m.addConstr(lhs >= rhs, name=name)
    else:
        m.addConstr(lhs == rhs, name=name)

m.optimize()

status_names = {
    gp.GRB.LOADED: "LOADED",
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.CUTOFF: "CUTOFF",
    gp.GRB.ITERATION_LIMIT: "ITERATION_LIMIT",
    gp.GRB.NODE_LIMIT: "NODE_LIMIT",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.SOLUTION_LIMIT: "SOLUTION_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
    gp.GRB.NUMERIC: "NUMERIC",
    gp.GRB.SUBOPTIMAL: "SUBOPTIMAL",
    gp.GRB.USER_OBJ_LIMIT: "USER_OBJ_LIMIT"
}
status = status_names.get(m.Status, str(m.Status))

if m.SolCount > 0:
    raw_values = [var.X for var in x]
    projected_action = [1 if value >= 0.5 else 0 for value in raw_values]
    violations = []
    for name, sense, rhs, terms in constraints_data:
        lhs_value = sum(coef * raw_values[index] for index, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs_value - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs_value))
        else:
            violations.append(abs(lhs_value - rhs))
    for value in raw_values:
        violations.append(max(0.0, -value, value - 1.0))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(min(abs(value), abs(value - 1.0)) for value in raw_values)
    objective = m.ObjVal
else:
    projected_action = None
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
