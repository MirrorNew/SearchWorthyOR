import gurobipy as gp
import json

# REGION data
returns = [1014, 953, 911, 850, 789, 747, 686]
capital = [1, 2, 3, 4, 1, 2, 3]
risk = [4, 1, 3, 5, 2, 4, 1]

model = gp.Model("SWOR048_patched")
model.Params.OutputFlag = 0

# REGION variables
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

# REGION objective
model.setObjective(gp.quicksum(returns[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# REGION base_constraints
model.addConstr(gp.quicksum(x) == 3, name="c_position_count")
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(7)) <= 12, name="c_capital_limit")
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(7)) <= 15, name="c_risk_limit")
model.addConstr(x[0] + x[3] >= 1, name="c_core_A_or_D")

# REGION evidence_patch
model.addConstr(x[0] == 0, name="c_A_clean_vehicle_credit_cutoff")

# REGION solve_and_project
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
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, sum(capital[i] * values[i] for i in range(7)) - 12.0),
        max(0.0, sum(risk[i] * values[i] for i in range(7)) - 15.0),
        max(0.0, 1.0 - values[0] - values[3]),
        abs(values[0]),
        max(max(0.0, -value, value - 1.0) for value in values)
    ]
    integrality_violation = max(abs(value - round(value)) for value in values)
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": float(max(violations)),
        "integrality_violation": float(integrality_violation)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, sort_keys=True))
