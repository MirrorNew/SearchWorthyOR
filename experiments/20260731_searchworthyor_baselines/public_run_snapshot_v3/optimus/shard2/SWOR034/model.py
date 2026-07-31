import gurobipy as gp
from gurobipy import GRB
import json
import math

model = gp.Model("SWOR034_patched")
model.Params.OutputFlag = 0

utilities = [1000, 958, 897, 855, 794, 752, 691, 630]
x = [model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
model.update()

model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(8)), GRB.MAXIMIZE)

# REGION base_constraints
model.addConstr(gp.quicksum(x) <= 3, name="maximum_enabled_modules")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="zone_1_coverage")
model.addConstr(x[1] + x[4] + x[7] >= 1, name="zone_2_coverage")
model.addConstr(x[2] + x[5] >= 1, name="zone_3_coverage")
model.addConstr(x[0] - x[1] - x[4] <= 0, name="module_A_backhaul_requirement")
# END REGION base_constraints

# REGION policy_DOC_BA1D5E769FAB2344
model.addConstr(x[0] + x[1] <= 1, name="policy_A_B_mutual_exclusion")
# END REGION policy_DOC_BA1D5E769FAB2344

# REGION solve_and_report
model.optimize()

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected_action = [int(value >= 0.5) for value in values]
    objective = float(model.ObjVal)
else:
    values = [0.0] * 8
    projected_action = [0] * 8
    objective = None

violations = [
    max(0.0, sum(values) - 3.0),
    max(0.0, 1.0 - (values[0] + values[3] + values[6])),
    max(0.0, 1.0 - (values[1] + values[4] + values[7])),
    max(0.0, 1.0 - (values[2] + values[5])),
    max(0.0, values[0] - values[1] - values[4]),
    max(0.0, values[0] + values[1] - 1.0)
]
max_constraint_violation = max(violations)
integrality_violation = max(math.fabs(value - round(value)) for value in values)
status = "OPTIMAL" if model.Status == GRB.OPTIMAL else str(int(model.Status))

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
# END REGION solve_and_report
