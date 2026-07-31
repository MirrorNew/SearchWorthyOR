import gurobipy as gp
import json

# REGION: model_and_variables
model = gp.Model("SWOR076_patched")
model.Params.OutputFlag = 0
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

# REGION: single_objective
utilities = [1010, 949, 907, 846, 804, 743, 682, 640]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

# REGION: frozen_base_constraints
model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[1] >= 1, name="emergency_coverage")
model.addConstr(x[1] + x[2] >= 1, name="continuity_coverage")
model.addConstr(x[0] + x[2] >= 1, name="specialty_coverage")
model.addConstr(x[6] + x[7] <= 1, name="backup_G_H_mutex")

# REGION: evidence_DOC_5DDEA42FE0D45AE3
model.addConstr(x[0] + x[1] <= 1, name="policy_A_implies_not_B")

# REGION: solve_and_report
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
    raw = [float(v.X) for v in x]
    projected_action = [int(value >= 0.5) for value in raw]
    lhs_values = [
        sum(raw),
        raw[0] + raw[1],
        raw[1] + raw[2],
        raw[0] + raw[2],
        raw[6] + raw[7],
        raw[0] + raw[1]
    ]
    violations = [
        abs(lhs_values[0] - 3),
        max(0.0, 1 - lhs_values[1]),
        max(0.0, 1 - lhs_values[2]),
        max(0.0, 1 - lhs_values[3]),
        max(0.0, lhs_values[4] - 1),
        max(0.0, lhs_values[5] - 1)
    ]
    objective = float(model.ObjVal)
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in raw)
else:
    projected_action = [0] * 8
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
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
