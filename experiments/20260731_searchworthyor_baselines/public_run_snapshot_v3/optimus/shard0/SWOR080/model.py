import gurobipy
import json
import math

model = gurobipy.Model("SWOR080_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

returns = [1012, 951, 909, 848, 806, 745, 684, 642]
capital = [4, 1, 2, 3, 4, 1, 2, 3]
risk = [5, 2, 4, 1, 3, 5, 2, 4]

model.setObjective(gurobipy.quicksum(returns[i] * x[i] for i in range(8)), gurobipy.GRB.MAXIMIZE)
model.addConstr(gurobipy.quicksum(x) == 3, name="required_position_count")
model.addConstr(gurobipy.quicksum(capital[i] * x[i] for i in range(8)) <= 12, name="capital_capacity")
model.addConstr(gurobipy.quicksum(risk[i] * x[i] for i in range(8)) <= 15, name="risk_capacity")
model.addConstr(x[1] + x[4] + x[7] == 1, name="exactly_one_of_B_E_H")
# DOC-28920EAE9EE798CE: Section 30D and Section 45W branches for the same vehicle are mutually exclusive.
model.addConstr(x[0] + x[1] <= 1, name="same_vehicle_credit_branch_exclusivity")

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
    values = [x[i].X for i in range(8)]
    projected_action = [int(round(value)) for value in values]
    position_lhs = sum(values)
    capital_lhs = sum(capital[i] * values[i] for i in range(8))
    risk_lhs = sum(risk[i] * values[i] for i in range(8))
    group_lhs = values[1] + values[4] + values[7]
    exclusion_lhs = values[0] + values[1]
    bound_violation = max(max(0.0, -value, value - 1.0) for value in values)
    violations = [
        abs(position_lhs - 3.0),
        max(0.0, capital_lhs - 12.0),
        max(0.0, risk_lhs - 15.0),
        abs(group_lhs - 1.0),
        max(0.0, exclusion_lhs - 1.0),
        bound_violation
    ]
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(value - round(value)) for value in values)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))
