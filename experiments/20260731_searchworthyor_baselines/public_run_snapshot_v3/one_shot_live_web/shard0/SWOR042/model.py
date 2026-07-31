import gurobipy as gp
import json
import math

m = gp.Model("SWOR042_patched")
m.Params.OutputFlag = 0

x = [m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

benefit = [1002, 960, 899, 857, 796, 735]
m.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

m.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
m.addConstr(x[0] + x[3] >= 1, name="cover_period_1")
m.addConstr(x[1] + x[4] >= 1, name="cover_period_2")
m.addConstr(x[2] + x[5] >= 1, name="cover_period_3")
m.addConstr(x[0] + x[3] >= 1, name="core_A_or_backup_D")
m.addConstr(x[0] + x[1] <= 1, name="policy_unpaid_meal_no_oncall")

m.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(m.Status, str(m.Status))

if m.SolCount > 0:
    values = [v.X for v in x]
    projected = [int(round(value)) for value in values]
    lhs_values = [
        sum(values),
        values[0] + values[3],
        values[1] + values[4],
        values[2] + values[5],
        values[0] + values[3],
        values[0] + values[1]
    ]
    violations = [
        abs(lhs_values[0] - 3),
        max(0.0, 1 - lhs_values[1]),
        max(0.0, 1 - lhs_values[2]),
        max(0.0, 1 - lhs_values[3]),
        max(0.0, 1 - lhs_values[4]),
        max(0.0, lhs_values[5] - 1)
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = m.ObjVal
else:
    projected = []
    max_constraint_violation = None
    integrality_violation = None
    objective = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))