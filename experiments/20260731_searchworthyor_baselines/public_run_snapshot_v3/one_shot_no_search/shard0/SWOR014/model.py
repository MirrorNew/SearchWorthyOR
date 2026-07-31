import gurobipy as gp
from gurobipy import GRB
import json
import math

# REGION model_and_variables
model = gp.Model("SWOR014")
model.Params.OutputFlag = 0
x = [model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

# REGION objective
benefits = [1010, 949, 907, 846, 804, 743, 682, 640]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(8)), GRB.MAXIMIZE)

# REGION base_constraints
model.addConstr(gp.quicksum(x) == 3, name="c_select_3")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="c_period_1_cover")
model.addConstr(x[1] + x[4] + x[7] >= 1, name="c_period_2_cover")
model.addConstr(x[2] + x[5] >= 1, name="c_period_3_cover")
model.addConstr(x[1] + x[4] + x[7] == 1, name="c_exactly_one_B_E_H")

# REGION solve_and_report
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
    raw_values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in raw_values]
    objective = float(model.ObjVal)

    lhs_values = [
        sum(raw_values),
        raw_values[0] + raw_values[3] + raw_values[6],
        raw_values[1] + raw_values[4] + raw_values[7],
        raw_values[2] + raw_values[5],
        raw_values[1] + raw_values[4] + raw_values[7]
    ]
    senses = ["==", ">=", ">=", ">=", "=="]
    rhs_values = [3.0, 1.0, 1.0, 1.0, 1.0]
    violations = []
    for lhs, sense, rhs in zip(lhs_values, senses, rhs_values):
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in raw_values)
else:
    projected_action = [0] * 8
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
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
