import gurobipy as gp
import json
import math

model = gp.Model("SWOR090_patched")

# [VARIABLES]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

# [OBJECTIVE]
returns = [1005, 963, 902, 841, 799, 738, 696, 635]
model.setObjective(gp.quicksum(returns[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

# [C1_HOLD_EXACTLY_3]
model.addConstr(gp.quicksum(x) == 3, name="hold_exactly_3")

# [C2_CAPITAL_CAPACITY]
capital = [2, 3, 4, 1, 2, 3, 4, 1]
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(8)) <= 12, name="capital_capacity")

# [C3_RISK_CAPACITY]
risk = [4, 1, 3, 5, 2, 4, 1, 3]
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(8)) <= 15, name="risk_capacity")

# [C4_CORE_A_OR_D]
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_D")

# [C5_EXTERNAL_A_B_MUTEX]
model.addConstr(x[0] + x[1] <= 1, name="external_A_B_mutex")

model.ModelSense = gp.GRB.MAXIMIZE
model.optimize()

status = "OPTIMAL" if model.Status == gp.GRB.OPTIMAL else str(model.Status)
if model.SolCount > 0:
    raw = [float(v.X) for v in x]
    projected_action = [int(round(value)) for value in raw]
    objective = float(model.ObjVal)
    lhs_values = [
        sum(raw),
        sum(capital[i] * raw[i] for i in range(8)),
        sum(risk[i] * raw[i] for i in range(8)),
        raw[0] + raw[3],
        raw[0] + raw[1]
    ]
    violations = [
        abs(lhs_values[0] - 3),
        max(0.0, lhs_values[1] - 12),
        max(0.0, lhs_values[2] - 15),
        max(0.0, 1 - lhs_values[3]),
        max(0.0, lhs_values[4] - 1)
    ]
    max_constraint_violation = float(max(violations))
    integrality_violation = float(max(abs(value - round(value)) for value in raw))
else:
    projected_action = [0 for _ in range(8)]
    objective = None
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))