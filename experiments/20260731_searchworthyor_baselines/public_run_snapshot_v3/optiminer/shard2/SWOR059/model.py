import gurobipy as gp
import json
import math

# [DATA] Frozen candidate data from the public task.
REWARDS = [1000, 958, 897, 855, 794, 752]
RESOURCE_USAGE = [1, 2, 3, 4, 1, 2]
CATEGORY = ["基础类别", "基础类别", "基础类别", "基础类别", "保障类别1", "保障类别2"]

model = gp.Model("SWOR059_patched")
model.Params.OutputFlag = 0

# [VARIABLES] Binary decisions in action_projection order.
x = [
    model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}")
    for i in range(6)
]

# [OBJECTIVE] Single objective: maximize total transportation-service reward.
model.setObjective(
    gp.quicksum(REWARDS[i] * x[i] for i in range(6)),
    gp.GRB.MAXIMIZE,
)

# [BASE-C1] Transportation-chain segment 1.
model.addConstr(x[0] + x[3] == 1, name="chain_segment_1_exactly_one")
# [BASE-C2] Transportation-chain segment 2.
model.addConstr(x[1] + x[4] == 1, name="chain_segment_2_exactly_one")
# [BASE-C3] Transportation-chain segment 3.
model.addConstr(x[2] + x[5] == 1, name="chain_segment_3_exactly_one")
# [POLICY-C4] DOC-1AAB4541D0AFF6A2: selecting A excludes B.
model.addConstr(x[0] + x[1] <= 1, name="policy_A_excludes_B")

# [SOLVE-OUTPUT]
model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in raw]
    objective_value = float(model.ObjVal)
    if not math.isfinite(objective_value):
        objective_value = None

    rows = [
        ({0: 1.0, 3: 1.0}, "==", 1.0),
        ({1: 1.0, 4: 1.0}, "==", 1.0),
        ({2: 1.0, 5: 1.0}, "==", 1.0),
        ({0: 1.0, 1: 1.0}, "<=", 1.0),
    ]
    violations = [max(0.0, -value, value - 1.0) for value in raw]
    for coefficients, row_sense, rhs in rows:
        lhs = sum(coefficient * raw[index] for index, coefficient in coefficients.items())
        if row_sense == "==":
            violations.append(abs(lhs - rhs))
        elif row_sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in raw)
else:
    objective_value = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective_value,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}, ensure_ascii=False, sort_keys=True))
