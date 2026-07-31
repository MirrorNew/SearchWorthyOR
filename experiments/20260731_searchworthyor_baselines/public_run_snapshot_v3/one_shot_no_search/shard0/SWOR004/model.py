import gurobipy as gp
import json
import math

model = gp.Model("SWOR004")
model.Params.OutputFlag = 0

# REGION variables
names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]

# REGION objective
profits = [1010, 949, 907, 846, 804, 743, 682]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# REGION select_exactly_3
model.addConstr(gp.quicksum(x[i] for i in range(7)) == 3, name="select_exactly_3")

# REGION front_supply_min_1
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="front_supply_min_1")

# REGION back_supply_min_1
model.addConstr(x[1] + x[2] + x[4] >= 1, name="back_supply_min_1")

# REGION core_abc_min_2
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_abc_min_2")

# REGION solve_and_report
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
    values = [float(var.X) for var in x]
    projected_action = [1 if value >= 0.5 else 0 for value in values]
    lhs_values = [
        sum(values),
        values[0] + values[1] + values[3] + values[6],
        values[1] + values[2] + values[4],
        values[0] + values[1] + values[2]
    ]
    violations = [
        abs(lhs_values[0] - 3.0),
        max(0.0, 1.0 - lhs_values[1]),
        max(0.0, 1.0 - lhs_values[2]),
        max(0.0, 2.0 - lhs_values[3])
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal)
else:
    projected_action = []
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
print(json.dumps(result, ensure_ascii=False))
