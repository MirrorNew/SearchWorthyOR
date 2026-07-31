import gurobipy
import json
import math

# [variables]
model = gurobipy.Model("SWOR048_patched")
model.Params.OutputFlag = 0
names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
x = {name: model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

# [objective]
returns = {"x_0": 1014, "x_1": 953, "x_2": 911, "x_3": 850, "x_4": 789, "x_5": 747, "x_6": 686}
model.setObjective(gurobipy.quicksum(returns[name] * x[name] for name in names), gurobipy.GRB.MAXIMIZE)

# [constraint:position_count]
model.addConstr(gurobipy.quicksum(x[name] for name in names) == 3, name="position_count")

# [constraint:capital_limit]
capital = {"x_0": 1, "x_1": 2, "x_2": 3, "x_3": 4, "x_4": 1, "x_5": 2, "x_6": 3}
model.addConstr(gurobipy.quicksum(capital[name] * x[name] for name in names) <= 12, name="capital_limit")

# [constraint:risk_limit]
risk = {"x_0": 4, "x_1": 1, "x_2": 3, "x_3": 5, "x_4": 2, "x_5": 4, "x_6": 1}
model.addConstr(gurobipy.quicksum(risk[name] * x[name] for name in names) <= 15, name="risk_limit")

# [constraint:core_or_backup]
model.addConstr(x["x_0"] + x["x_3"] >= 1, name="core_or_backup")

# [constraint:clean_vehicle_acquisition_deadline]
model.addConstr(x["x_0"] == 0, name="clean_vehicle_acquisition_deadline")

model.optimize()

status = "OPTIMAL" if model.Status == gurobipy.GRB.OPTIMAL else str(model.Status)
if model.SolCount > 0:
    values = [float(x[name].X) for name in names]
    projected = [int(round(value)) for value in values]
    position_violation = abs(sum(values) - 3.0)
    capital_violation = max(0.0, sum(capital[name] * values[i] for i, name in enumerate(names)) - 12.0)
    risk_violation = max(0.0, sum(risk[name] * values[i] for i, name in enumerate(names)) - 15.0)
    core_violation = max(0.0, 1.0 - values[0] - values[3])
    deadline_violation = abs(values[0])
    max_constraint_violation = max(position_violation, capital_violation, risk_violation, core_violation, deadline_violation)
    integrality_violation = max(abs(value - round(value)) for value in values)
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected,
        "max_constraint_violation": float(max_constraint_violation),
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
print(json.dumps(result, ensure_ascii=False))
