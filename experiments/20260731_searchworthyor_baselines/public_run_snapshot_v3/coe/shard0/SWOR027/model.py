import gurobipy as gp
import json
import math

model = gp.Model("SWOR027")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = model.addVars(8, vtype=gp.GRB.BINARY, lb=0, ub=1, name="x")
benefit = [1008, 947, 905, 844, 802, 741, 699, 638]

model.setObjective(
    gp.quicksum(benefit[i] * x[i] for i in range(8)),
    gp.GRB.MAXIMIZE,
)

model.addConstr(
    gp.quicksum(x[i] for i in range(8)) == 3,
    name="base_exactly_three",
)
model.addConstr(
    x[0] + x[1] + x[3] + x[6] >= 1,
    name="base_front_coverage",
)
model.addConstr(
    x[1] + x[2] + x[4] + x[7] >= 1,
    name="base_back_coverage",
)
model.addConstr(
    x[0] + x[3] >= 1,
    name="base_core_or_backup",
)
model.addConstr(
    x[0] == 0,
    name="evidence_A_ineligible",
)

model.optimize()

if model.Status != gp.GRB.OPTIMAL:
    raise RuntimeError("Optimization did not reach OPTIMAL status: " + str(model.Status))

values = [float(x[i].X) for i in range(8)]
projected_action = [int(round(value)) for value in values]

checks = [
    (sum(values), "==", 3.0),
    (values[0] + values[1] + values[3] + values[6], ">=", 1.0),
    (values[1] + values[2] + values[4] + values[7], ">=", 1.0),
    (values[0] + values[3], ">=", 1.0),
    (values[0], "==", 0.0),
]

violations = []
for lhs, sense, rhs in checks:
    if sense == "==":
        violations.append(abs(lhs - rhs))
    elif sense == ">=":
        violations.append(max(0.0, rhs - lhs))
    else:
        violations.append(max(0.0, lhs - rhs))

for value in values:
    violations.append(max(0.0, -value, value - 1.0))

integrality_violation = max(abs(value - round(value)) for value in values)
max_constraint_violation = max(violations) if violations else 0.0

result = {
    "status": "OPTIMAL",
    "objective": float(model.ObjVal),
    "projected_action": projected_action,
    "max_constraint_violation": float(max_constraint_violation),
    "integrality_violation": float(integrality_violation),
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
