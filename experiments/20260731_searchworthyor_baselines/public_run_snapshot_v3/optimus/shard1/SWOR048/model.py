import gurobipy
import json
import math

# region variables
model = gurobipy.Model("SWOR048_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0
x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

# region objective
returns = [1014, 953, 911, 850, 789, 747, 686]
model.setObjective(gurobipy.quicksum(returns[i] * x[i] for i in range(7)), gurobipy.GRB.MAXIMIZE)

# region constraints.position
model.addConstr(gurobipy.quicksum(x) == 3, name="exactly_three_positions")

# region constraints.capital
capital = [1, 2, 3, 4, 1, 2, 3]
model.addConstr(gurobipy.quicksum(capital[i] * x[i] for i in range(7)) <= 12, name="capital_limit")

# region constraints.risk
risk = [4, 1, 3, 5, 2, 4, 1]
model.addConstr(gurobipy.quicksum(risk[i] * x[i] for i in range(7)) <= 15, name="risk_limit")

# region constraints.core_or_backup
model.addConstr(x[0] + x[3] >= 1, name="core_or_backup")

# region evidence_patch.none
# No external equation is instantiated: the authoritative rule is vehicle-specific,
# while the supplied facts establish no same-vehicle cross-branch combination.

# region solve_output
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
    projected = [int(round(value)) for value in values]
    activities = [
        sum(values),
        sum(capital[i] * values[i] for i in range(7)),
        sum(risk[i] * values[i] for i in range(7)),
        values[0] + values[3]
    ]
    violations = [
        abs(activities[0] - 3),
        max(0.0, activities[1] - 12),
        max(0.0, activities[2] - 15),
        max(0.0, 1 - activities[3])
    ]
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(value - round(value)) for value in values)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": None,
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))
