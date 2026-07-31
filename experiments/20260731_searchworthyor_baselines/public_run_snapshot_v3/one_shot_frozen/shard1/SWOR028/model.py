import gurobipy as gp
import json
import math

model = gp.Model("SWOR028_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
benefits = [1013, 952, 910, 849, 788, 746, 685, 643]

model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="facility_count")
model.addConstr(x[0] + x[2] + x[4] + x[6] >= 1, name="service_area_1")
model.addConstr(x[1] + x[3] + x[5] + x[7] >= 1, name="service_area_2")
model.addConstr(x[6] + x[7] <= 1, name="backup_mutual_exclusion")
model.addConstr(x[6] + x[7] >= 1, name="policy_safeguard_min")

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
    projected_action = [1 if value >= 0.5 else 0 for value in values]
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, 1.0 - (values[0] + values[2] + values[4] + values[6])),
        max(0.0, 1.0 - (values[1] + values[3] + values[5] + values[7])),
        max(0.0, values[6] + values[7] - 1.0),
        max(0.0, 1.0 - (values[6] + values[7]))
    ]
    objective = float(model.ObjVal)
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    projected_action = [0] * 8
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