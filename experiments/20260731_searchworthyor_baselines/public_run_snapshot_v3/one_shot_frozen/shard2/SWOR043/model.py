import gurobipy as gp
import json
import math

model = gp.Model("SWOR043")
model.Params.OutputFlag = 0

semantic_names = ["匹配A", "匹配B", "匹配C", "匹配D", "匹配E", "匹配F"]
profits = [1010, 949, 907, 846, 804, 743]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="frozen_exactly_three")
model.addConstr(x[0] + x[3] <= 1, name="subject1_a_d_at_most_one")
model.addConstr(x[1] + x[4] <= 1, name="subject2_b_e_at_most_one")
model.addConstr(x[2] + x[5] <= 1, name="subject3_c_f_at_most_one")
model.addConstr(x[0] + x[3] >= 1, name="frozen_core_a_d_at_least_one")
model.addConstr(x[0] + x[1] <= 1, name="policy_a_blocks_b")

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
    values = [x[i].X for i in range(6)]
    projected_action = [int(round(value)) for value in values]
    violations = [
        abs(sum(values) - 3),
        max(0.0, values[0] + values[3] - 1),
        max(0.0, values[1] + values[4] - 1),
        max(0.0, values[2] + values[5] - 1),
        max(0.0, 1 - values[0] - values[3]),
        max(0.0, values[0] + values[1] - 1)
    ]
    violations.extend(max(0.0, -value, value - 1) for value in values)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal if math.isfinite(model.ObjVal) else None
    max_constraint_violation = max(violations)
else:
    projected_action = [0, 0, 0, 0, 0, 0]
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
