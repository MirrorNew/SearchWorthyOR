import gurobipy as gp
import json
import math

model = gp.Model("SWOR063_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
returns = [1009, 948, 906, 845, 803, 742]
capital = [4, 1, 2, 3, 4, 1]
risk = [2, 4, 1, 3, 5, 2]

model.setObjective(gp.quicksum(returns[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="required_positions")
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(6)) <= 12, name="capital_limit")
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(6)) <= 15, name="risk_limit")
model.addConstr(x[4] + x[5] <= 1, name="terminal_reserve_mutex")
model.addConstr(x[0] == 0, name="policy_A_ineligible")

model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
    gp.GRB.SUBOPTIMAL: "SUBOPTIMAL"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [x[i].X for i in range(6)]
    projected_action = [int(v >= 0.5) for v in values]
    violations = [
        abs(sum(values) - 3),
        max(0.0, sum(capital[i] * values[i] for i in range(6)) - 12),
        max(0.0, sum(risk[i] * values[i] for i in range(6)) - 15),
        max(0.0, values[4] + values[5] - 1),
        abs(values[0])
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in values)
    objective = model.ObjVal if math.isfinite(model.ObjVal) else None
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