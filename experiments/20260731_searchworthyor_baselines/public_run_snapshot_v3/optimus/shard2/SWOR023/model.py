import gurobipy as gp
import json
import math

model = gp.Model("SWOR023_patched")
model.Params.OutputFlag = 0

utilities = [1012, 951, 909, 848, 806, 745, 684]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
model.update()

model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[1] >= 1, name="emergency_coverage")
model.addConstr(x[1] + x[2] >= 1, name="continuity_coverage")
model.addConstr(x[0] + x[2] >= 1, name="specialty_coverage")

# Evidence applicability gate resolved upstream: DOC-CBCBD22409439B8D is the unique applicable policy.
# code_region: policy_disqualify_A
model.addConstr(x[0] == 0, name="policy_disqualify_A")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(value >= 0.5) for value in values]
    objective = float(model.ObjVal)

    violations = []
    violations.append(abs(sum(values) - 3.0))
    violations.append(max(0.0, 1.0 - (values[0] + values[1])))
    violations.append(max(0.0, 1.0 - (values[1] + values[2])))
    violations.append(max(0.0, 1.0 - (values[0] + values[2])))
    violations.append(abs(values[0]))
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))

    max_constraint_violation = float(max(violations))
    integrality_violation = float(max(abs(value - round(value)) for value in values))
else:
    objective = None
    projected_action = []
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