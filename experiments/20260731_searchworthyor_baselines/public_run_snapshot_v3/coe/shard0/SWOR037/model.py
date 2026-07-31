import gurobipy as gp
import json
import math

ACTION_PROJECTION = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
OBJECTIVE_CONSTANT = 0.0
OBJECTIVE_TERMS = {
    "x_0": 1013.0,
    "x_1": 952.0,
    "x_2": 910.0,
    "x_3": 849.0,
    "x_4": 788.0,
    "x_5": 746.0,
    "x_6": 685.0,
    "x_7": 643.0,
}
CONSTRAINTS = [
    ("base_max_three_modules", "<=", 3.0, {"x_0": 1.0, "x_1": 1.0, "x_2": 1.0, "x_3": 1.0, "x_4": 1.0, "x_5": 1.0, "x_6": 1.0, "x_7": 1.0}),
    ("base_zone_1_coverage", ">=", 1.0, {"x_0": 1.0, "x_3": 1.0, "x_6": 1.0}),
    ("base_zone_2_coverage", ">=", 1.0, {"x_1": 1.0, "x_4": 1.0, "x_7": 1.0}),
    ("base_zone_3_coverage", ">=", 1.0, {"x_2": 1.0, "x_5": 1.0}),
    ("base_A_requires_B_or_E", "<=", 0.0, {"x_0": 1.0, "x_1": -1.0, "x_4": -1.0}),
    ("base_A_or_D", ">=", 1.0, {"x_0": 1.0, "x_3": 1.0}),
]

# 冻结证据均未同时通过权限、时点、主体/活动及关联核验。
APPLIED_POLICY_EVIDENCE = []
PATCH_OPS = []

model = gp.Model("SWOR037")
model.Params.OutputFlag = 0
x = model.addVars(ACTION_PROJECTION, vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name="x")

objective = gp.quicksum(OBJECTIVE_TERMS[name] * x[name] for name in ACTION_PROJECTION)
model.setObjective(objective + OBJECTIVE_CONSTANT, gp.GRB.MAXIMIZE)

for constraint_name, constraint_sense, rhs, terms in CONSTRAINTS:
    expression = gp.quicksum(coefficient * x[name] for name, coefficient in terms.items())
    if constraint_sense == "<=":
        model.addConstr(expression <= rhs, name=constraint_name)
    elif constraint_sense == ">=":
        model.addConstr(expression >= rhs, name=constraint_name)
    elif constraint_sense == "==":
        model.addConstr(expression == rhs, name=constraint_name)
    else:
        raise ValueError("Unsupported constraint sense: " + constraint_sense)

if APPLIED_POLICY_EVIDENCE or PATCH_OPS:
    raise AssertionError("NO-OP evidence adjudication was not preserved")

model.optimize()
if model.Status != gp.GRB.OPTIMAL:
    raise RuntimeError("Gurobi did not return OPTIMAL; status=" + str(model.Status))

raw_values = {name: float(x[name].X) for name in ACTION_PROJECTION}
projected_action = [1 if raw_values[name] >= 0.5 else 0 for name in ACTION_PROJECTION]
integrality_violation = max(
    min(abs(raw_values[name]), abs(raw_values[name] - 1.0))
    for name in ACTION_PROJECTION
)

max_constraint_violation = 0.0
for constraint_name, constraint_sense, rhs, terms in CONSTRAINTS:
    lhs = sum(coefficient * raw_values[name] for name, coefficient in terms.items())
    if constraint_sense == "<=":
        violation = max(0.0, lhs - rhs)
    elif constraint_sense == ">=":
        violation = max(0.0, rhs - lhs)
    else:
        violation = abs(lhs - rhs)
    max_constraint_violation = max(max_constraint_violation, violation)

recomputed_objective = OBJECTIVE_CONSTANT + sum(
    OBJECTIVE_TERMS[name] * raw_values[name] for name in ACTION_PROJECTION
)
if not math.isclose(model.ObjVal, recomputed_objective, rel_tol=0.0, abs_tol=1e-6):
    raise AssertionError("Objective-value verification failed")

result = {
    "status": "OPTIMAL",
    "objective": float(model.ObjVal),
    "projected_action": projected_action,
    "max_constraint_violation": float(max_constraint_violation),
    "integrality_violation": float(integrality_violation),
    "applied_policy_evidence": APPLIED_POLICY_EVIDENCE,
    "patch_ops": PATCH_OPS,
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
