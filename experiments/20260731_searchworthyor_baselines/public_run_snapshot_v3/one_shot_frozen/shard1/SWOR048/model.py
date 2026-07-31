import gurobipy as gp
import json
import math

model = gp.Model("SWOR048_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

objective_coefficients = [1014, 953, 911, 850, 789, 747, 686]
model.setObjective(gp.quicksum(objective_coefficients[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="c_cardinality")
model.addConstr(x[0] + 2*x[1] + 3*x[2] + 4*x[3] + x[4] + 2*x[5] + 3*x[6] <= 12, name="c_capital")
model.addConstr(4*x[0] + x[1] + 3*x[2] + 5*x[3] + 2*x[4] + 4*x[5] + x[6] <= 15, name="c_risk")
model.addConstr(x[0] + x[3] >= 1, name="c_core_A_or_D")

# EVIDENCE_GATE_NO_SAME_VEHICLE_PAIR: no constraint is emitted because the
# supplied facts do not identify two strategies as competing credit branches
# for the same vehicle.

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
    raw = [v.X for v in x]
    projected_action = [int(round(value)) for value in raw]
    cardinality = sum(raw)
    capital = raw[0] + 2*raw[1] + 3*raw[2] + 4*raw[3] + raw[4] + 2*raw[5] + 3*raw[6]
    risk = 4*raw[0] + raw[1] + 3*raw[2] + 5*raw[3] + 2*raw[4] + 4*raw[5] + raw[6]
    core = raw[0] + raw[3]
    violations = [
        abs(cardinality - 3),
        max(0.0, capital - 12),
        max(0.0, risk - 15),
        max(0.0, 1 - core)
    ]
    violations.extend(max(0.0, -value, value - 1) for value in raw)
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in raw)
    objective = model.ObjVal
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
