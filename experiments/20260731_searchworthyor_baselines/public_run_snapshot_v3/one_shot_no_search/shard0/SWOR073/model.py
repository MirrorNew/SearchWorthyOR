import gurobipy as gp
import json
import math

model = gp.Model("SWOR073")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
model.setObjective(
    1004 * x[0] + 962 * x[1] + 901 * x[2] +
    859 * x[3] + 798 * x[4] + 737 * x[5],
    gp.GRB.MAXIMIZE
)

model.addConstr(gp.quicksum(x) == 3, name="complete_exactly_3")
model.addConstr(x[0] + x[3] <= 1, name="subject_1_A_D_at_most_1")
model.addConstr(x[1] + x[4] <= 1, name="subject_2_B_E_at_most_1")
model.addConstr(x[2] + x[5] <= 1, name="subject_3_C_F_at_most_1")
model.addConstr(x[4] + x[5] <= 1, name="terminal_E_F_at_most_1")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))
has_solution = model.SolCount > 0
raw = [v.X for v in x] if has_solution else [0.0] * 6
projected = [int(round(value)) for value in raw]
objective = float(model.ObjVal) if has_solution else None

violations = [
    abs(sum(raw) - 3.0),
    max(0.0, raw[0] + raw[3] - 1.0),
    max(0.0, raw[1] + raw[4] - 1.0),
    max(0.0, raw[2] + raw[5] - 1.0),
    max(0.0, raw[4] + raw[5] - 1.0)
]
max_constraint_violation = max(violations)
integrality_violation = max(abs(value - round(value)) for value in raw)

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
