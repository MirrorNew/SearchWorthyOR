import gurobipy as gp
from gurobipy import GRB
import json
import math

model = gp.Model("SWOR060")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

objective_coefficients = [1011, 950, 908, 847, 805, 744, 683]
model.setObjective(gp.quicksum(objective_coefficients[i] * x[i] for i in range(7)), GRB.MAXIMIZE)

constraint_specs = []

expr_1 = x[0] + x[3] + x[6]
model.addConstr(expr_1 == 1, name="transport_segment_1_exactly_one")
constraint_specs.append((expr_1, "==", 1.0))

expr_2 = x[1] + x[4]
model.addConstr(expr_2 == 1, name="transport_segment_2_exactly_one")
constraint_specs.append((expr_2, "==", 1.0))

expr_3 = x[2] + x[5]
model.addConstr(expr_3 == 1, name="transport_segment_3_exactly_one")
constraint_specs.append((expr_3, "==", 1.0))

expr_4 = x[1] + x[4] + x[6]
model.addConstr(expr_4 == 1, name="core_backup_emergency_exactly_one")
constraint_specs.append((expr_4, "==", 1.0))

model.optimize()

status_names = {
    GRB.OPTIMAL: "OPTIMAL",
    GRB.INFEASIBLE: "INFEASIBLE",
    GRB.INF_OR_UNBD: "INF_OR_UNBD",
    GRB.UNBOUNDED: "UNBOUNDED",
    GRB.TIME_LIMIT: "TIME_LIMIT",
    GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    projected_action = [int(round(variable.X)) for variable in x]
    objective = float(model.ObjVal)
    violations = []
    for expression, constraint_sense, rhs in constraint_specs:
        lhs = float(expression.getValue())
        if constraint_sense == "==":
            violation = abs(lhs - rhs)
        elif constraint_sense == "<=":
            violation = max(0.0, lhs - rhs)
        else:
            violation = max(0.0, rhs - lhs)
        violations.append(violation)
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(variable.X - round(variable.X)) for variable in x)
else:
    projected_action = []
    objective = None
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
