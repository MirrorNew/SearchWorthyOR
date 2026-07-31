import gurobipy
import json
import math

model = gurobipy.Model("SWOR019_patched")
model.Params.OutputFlag = 0

# VAR: binary enablement decisions in A-through-G order
x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
model.update()

# OBJ: maximize total energy-service revenue
revenues = [1011, 950, 908, 847, 805, 744, 683]
model.setObjective(gurobipy.quicksum(revenues[i] * x[i] for i in range(7)), gurobipy.GRB.MAXIMIZE)

# C1: maximum enabled plans
model.addConstr(gurobipy.quicksum(x) <= 3, name="maximum_enabled_plans")

# C2: grid-resource capacity
usage = [4, 1, 2, 3, 4, 1, 2]
model.addConstr(gurobipy.quicksum(usage[i] * x[i] for i in range(7)) <= 7, name="grid_resource_capacity")

# C3: minimum clean capability
model.addConstr(x[0] + x[3] + x[6] >= 1, name="minimum_clean_capability")

# C4: minimum reserve capability
model.addConstr(x[1] + x[4] >= 1, name="minimum_reserve_capability")

# C5: terminal backup mutual exclusion
model.addConstr(x[5] + x[6] <= 1, name="terminal_backup_mutual_exclusion")

# C6: applicable external guarantee requirement
model.addConstr(x[5] + x[6] >= 1, name="external_guarantee_minimum")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

# RESULT: project the solved decision to A-through-G order and audit feasibility
if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in values]
    lhs_values = [
        sum(values),
        sum(usage[i] * values[i] for i in range(7)),
        values[0] + values[3] + values[6],
        values[1] + values[4],
        values[5] + values[6],
        values[5] + values[6]
    ]
    senses = ["<=", "<=", ">=", ">=", "<=", ">="]
    rhs_values = [3.0, 7.0, 1.0, 1.0, 1.0, 1.0]
    violations = []
    for lhs, sense, rhs in zip(lhs_values, senses, rhs_values):
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(math.fabs(v - round(v)) for v in values)
    objective = float(model.ObjVal)
else:
    projected_action = None
    max_constraint_violation = None
    integrality_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))