import gurobipy as gp
import json

# VARIABLES
model = gp.Model("SWOR061_patched")
model.Params.OutputFlag = 0
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

# OBJECTIVE
benefits = [1017, 956, 895, 853, 792, 750, 689, 647]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

# BASE_CONSTRAINTS
model.addConstr(gp.quicksum(x) <= 3, name="max_enabled_modes")
capacity = [1, 2, 3, 4, 1, 2, 3, 4]
model.addConstr(gp.quicksum(capacity[i] * x[i] for i in range(8)) <= 6, name="equipment_capacity")

# EVIDENCE_PATCH_DOC_42134E8F5FC7EDF8
model.addConstr(x[0] == 0, name="eligibility_mode_A")

# SOLVE
model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(value >= 0.5) for value in values]
    count_violation = max(0.0, sum(values) - 3.0)
    capacity_violation = max(0.0, sum(capacity[i] * values[i] for i in range(8)) - 6.0)
    eligibility_violation = abs(values[0])
    bound_violation = max(max(0.0, -value, value - 1.0) for value in values)
    max_constraint_violation = max(count_violation, capacity_violation, eligibility_violation, bound_violation)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal)
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0, 0]
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
print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))