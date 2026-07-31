import gurobipy as gp
import json
import math

benefits = [1009, 948, 906, 845, 803, 742, 700, 639]
model = gp.Model("SWOR084_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(x[0] + x[3] + x[6] == 1, name="segment_1_exactly_one")
model.addConstr(x[1] + x[4] + x[7] == 1, name="segment_2_exactly_one")
model.addConstr(x[2] + x[5] == 1, name="segment_3_exactly_one")
model.addConstr(x[0] + x[1] <= 1, name="policy_incompatibility_A_B")

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
    values = [float(var.X) for var in x]
    projected_action = [int(value >= 0.5) for value in values]
    objective = float(model.ObjVal)

    lhs_values = [
        values[0] + values[3] + values[6],
        values[1] + values[4] + values[7],
        values[2] + values[5],
        values[0] + values[1]
    ]
    violations = [
        abs(lhs_values[0] - 1.0),
        abs(lhs_values[1] - 1.0),
        abs(lhs_values[2] - 1.0),
        max(0.0, lhs_values[3] - 1.0)
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
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
