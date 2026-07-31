import gurobipy
import json
import math

model = gurobipy.Model("SWOR021_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

objective_coefficients = [1018, 957, 896, 854, 793, 751, 690]
model.setObjective(
    gurobipy.quicksum(objective_coefficients[i] * x[i] for i in range(7)),
    gurobipy.GRB.MAXIMIZE
)

model.addConstr(gurobipy.quicksum(x) <= 3, name="max_enabled_units")
model.addConstr(2*x[0] + 3*x[1] + 4*x[2] + x[3] + 2*x[4] + 3*x[5] + 4*x[6] <= 9, name="grid_resource_capacity")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="minimum_clean_capability")
model.addConstr(x[1] + x[4] >= 1, name="minimum_backup_capability")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="minimum_core_candidates")
model.addConstr(x[0] == 0, name="eligibility_energy_plan_A")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(value >= 0.5) for value in values]
    lhs_values = [
        sum(values),
        2*values[0] + 3*values[1] + 4*values[2] + values[3] + 2*values[4] + 3*values[5] + 4*values[6],
        values[0] + values[3] + values[6],
        values[1] + values[4],
        values[0] + values[1] + values[2],
        values[0]
    ]
    senses = ["<=", "<=", ">=", ">=", ">=", "=="]
    rhs_values = [3, 9, 1, 1, 2, 0]
    violations = []
    for lhs, sense, rhs in zip(lhs_values, senses, rhs_values):
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(min(abs(value), abs(value - 1.0)) for value in values)
    objective = model.ObjVal
else:
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None
    objective = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))