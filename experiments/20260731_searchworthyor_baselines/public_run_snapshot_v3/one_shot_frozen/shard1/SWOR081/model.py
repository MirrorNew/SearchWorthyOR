import gurobipy as gp
import json
import math

m = gp.Model("SWOR081_patched")
m.Params.OutputFlag = 0

x = [m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
m.setObjective(
    1017*x[0] + 956*x[1] + 895*x[2] + 853*x[3]
    + 792*x[4] + 750*x[5] + 689*x[6] + 647*x[7],
    gp.GRB.MAXIMIZE
)

m.addConstr(gp.quicksum(x) == 3, name="exactly_three_units")
m.addConstr(x[0] + x[1] >= 1, name="emergency_coverage")
m.addConstr(x[1] + x[2] >= 1, name="continuity_coverage")
m.addConstr(x[0] + x[2] >= 1, name="specialty_coverage")
m.addConstr(x[0] + x[1] + x[2] >= 2, name="at_least_two_core_units")
m.addConstr(x[0] + x[1] <= 1, name="policy_A_B_mutual_exclusion")

m.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(m.Status, str(m.Status))
objective = None
projected_action = []
max_constraint_violation = None
integrality_violation = None

if m.SolCount > 0:
    values = [v.X for v in x]
    projected_action = [int(round(value)) for value in values]
    objective = m.ObjVal
    lhs_values = [
        sum(values),
        values[0] + values[1],
        values[1] + values[2],
        values[0] + values[2],
        values[0] + values[1] + values[2],
        values[0] + values[1]
    ]
    violations = [
        abs(lhs_values[0] - 3),
        max(0.0, 1 - lhs_values[1]),
        max(0.0, 1 - lhs_values[2]),
        max(0.0, 1 - lhs_values[3]),
        max(0.0, 2 - lhs_values[4]),
        max(0.0, lhs_values[5] - 1)
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))
