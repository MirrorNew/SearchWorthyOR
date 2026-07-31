import gurobipy as gp
from gurobipy import GRB
import json
import math

model = gp.Model("SWOR011_patched")
model.Params.OutputFlag = 0

# REGION variables
x = [
    model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name="x_0"),
    model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name="x_1"),
    model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name="x_2"),
    model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name="x_3"),
    model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name="x_4"),
    model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name="x_5")
]

# REGION objective
model.setObjective(
    1016 * x[0] + 955 * x[1] + 894 * x[2] +
    852 * x[3] + 791 * x[4] + 749 * x[5],
    GRB.MAXIMIZE
)

# REGION base_constraints
model.addConstr(gp.quicksum(x) == 3, name="required_assignment_count")
model.addConstr(x[0] + x[3] <= 1, name="resource_subject_1_mutex")
model.addConstr(x[1] + x[4] <= 1, name="resource_subject_2_mutex")
model.addConstr(x[2] + x[5] <= 1, name="resource_subject_3_mutex")

# REGION policy_patch_DOC_431CE8108480F82B
model.addConstr(x[0] == 0, name="policy_match_A_ineligible")

model.optimize()

status_names = {
    GRB.OPTIMAL: "OPTIMAL",
    GRB.INFEASIBLE: "INFEASIBLE",
    GRB.INF_OR_UNBD: "INF_OR_UNBD",
    GRB.UNBOUNDED: "UNBOUNDED",
    GRB.TIME_LIMIT: "TIME_LIMIT",
    GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(value >= 0.5) for value in values]
    objective = float(model.ObjVal)

    row_specs = [
        ("==", 3.0, {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0}),
        ("<=", 1.0, {0: 1.0, 3: 1.0}),
        ("<=", 1.0, {1: 1.0, 4: 1.0}),
        ("<=", 1.0, {2: 1.0, 5: 1.0}),
        ("==", 0.0, {0: 1.0})
    ]
    violations = []
    for sense, rhs, terms in row_specs:
        lhs = sum(coef * values[index] for index, coef in terms.items())
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    projected_action = [0, 0, 0, 0, 0, 0]
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