import gurobipy as gp
import json
import math

m = gp.Model("SWOR070")
m.Params.OutputFlag = 0

x = [m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

m.setObjective(
    1001 * x[0] + 959 * x[1] + 898 * x[2] +
    856 * x[3] + 795 * x[4] + 753 * x[5],
    gp.GRB.MAXIMIZE
)

m.addConstr(gp.quicksum(x) <= 3, name="unit_count_limit")
m.addConstr(3*x[0] + 4*x[1] + x[2] + 2*x[3] + 3*x[4] + 4*x[5] <= 8, name="grid_resource_limit")
m.addConstr(x[0] + x[3] >= 1, name="clean_capability_minimum")
m.addConstr(x[1] + x[4] >= 1, name="reserve_capability_minimum")
m.addConstr(x[4] + x[5] <= 1, name="terminal_backup_exclusion")
m.addConstr(x[4] + x[5] >= 1, name="policy_safeguard_minimum")

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
    projected_action = [int(v >= 0.5) for v in values]
    lhs_values = [
        sum(values),
        3*values[0] + 4*values[1] + values[2] + 2*values[3] + 3*values[4] + 4*values[5],
        values[0] + values[3],
        values[1] + values[4],
        values[4] + values[5],
        values[4] + values[5]
    ]
    senses = ["<=", "<=", ">=", ">=", "<=", ">="]
    rhs_values = [3, 8, 1, 1, 1, 1]
    violations = []
    for lhs, sense, rhs in zip(lhs_values, senses, rhs_values):
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in values)
    objective = m.ObjVal
else:
    objective = None
    projected_action = None
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))
