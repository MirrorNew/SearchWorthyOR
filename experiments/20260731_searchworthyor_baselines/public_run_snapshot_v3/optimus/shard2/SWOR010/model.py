import gurobipy as gp
import json
import math

model = gp.Model("SWOR010_patched")
model.Params.OutputFlag = 0

# VARIABLES
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

# OBJECTIVE_PUBLIC_TASK
benefit = [1000, 958, 897, 855, 794, 752]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

# CONSTRAINT_REQUIRED_PACKAGE_COUNT
model.addConstr(gp.quicksum(x) == 3, name="required_package_count")

# CONSTRAINT_FRONT_PLAN_MINIMUM
model.addConstr(x[0] + x[1] + x[3] >= 1, name="front_plan_minimum")

# CONSTRAINT_BACK_PLAN_MINIMUM
model.addConstr(x[1] + x[2] + x[4] >= 1, name="back_plan_minimum")

# CONSTRAINT_CORE_CANDIDATE_MINIMUM
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_candidate_minimum")

# POLICY_DOC_ED9564F229928E20
model.addConstr(x[0] + x[1] <= 1, name="policy_A_trigger_prohibits_B")

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
    values = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in values]
    objective = float(model.ObjVal)
    lhs_values = [
        sum(values),
        values[0] + values[1] + values[3],
        values[1] + values[2] + values[4],
        values[0] + values[1] + values[2],
        values[0] + values[1]
    ]
    violations = [
        abs(lhs_values[0] - 3.0),
        max(0.0, 1.0 - lhs_values[1]),
        max(0.0, 1.0 - lhs_values[2]),
        max(0.0, 2.0 - lhs_values[3]),
        max(0.0, lhs_values[4] - 1.0)
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(min(abs(v), abs(v - 1.0)) for v in values)
else:
    objective = None
    projected_action = [0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))