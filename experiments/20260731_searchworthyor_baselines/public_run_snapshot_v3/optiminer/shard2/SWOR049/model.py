import gurobipy as gp
import json
import math

model = gp.Model("SWOR049_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

objective_coefficients = [1003, 961, 900, 858, 797, 736]
model.setObjective(gp.quicksum(objective_coefficients[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="position_count")
model.addConstr(x[0] + 2*x[1] + 3*x[2] + 4*x[3] + x[4] + 2*x[5] <= 12, name="capital_limit")
model.addConstr(5*x[0] + 2*x[1] + 4*x[2] + x[3] + 3*x[4] + 5*x[5] <= 15, name="risk_limit")
model.addConstr(x[1] + x[4] + x[5] == 1, name="core_backup_emergency_exactly_one")
model.addConstr(x[0] + x[1] <= 1, name="policy_A_excludes_B")

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
    values = [v.X for v in x]
    projected_action = [int(round(value)) for value in values]
    lhs_values = [
        sum(values),
        values[0] + 2*values[1] + 3*values[2] + 4*values[3] + values[4] + 2*values[5],
        5*values[0] + 2*values[1] + 4*values[2] + values[3] + 3*values[4] + 5*values[5],
        values[1] + values[4] + values[5],
        values[0] + values[1]
    ]
    violations = [
        abs(lhs_values[0] - 3),
        max(0.0, lhs_values[1] - 12),
        max(0.0, lhs_values[2] - 15),
        abs(lhs_values[3] - 1),
        max(0.0, lhs_values[4] - 1)
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
else:
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None
    objective = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))