import gurobipy as gp
import json
import math

model = gp.Model("SWOR093_patched")
model.Params.OutputFlag = 0

returns = [1016, 955, 894, 852, 791, 749]
capital = [2, 3, 4, 1, 2, 3]
risk = [3, 5, 2, 4, 1, 3]

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_" + str(i)) for i in range(6)]
model.setObjective(gp.quicksum(returns[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="position_count")
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(6)) <= 12, name="capital_limit")
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(6)) <= 15, name="risk_limit")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="minimum_core_count")
model.addConstr(x[0] + x[1] <= 1, name="evidence_AB_mutual_exclusion")

model.optimize()

status_names = {
    gp.GRB.LOADED: "LOADED",
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.CUTOFF: "CUTOFF",
    gp.GRB.ITERATION_LIMIT: "ITERATION_LIMIT",
    gp.GRB.NODE_LIMIT: "NODE_LIMIT",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.SOLUTION_LIMIT: "SOLUTION_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
    gp.GRB.NUMERIC: "NUMERIC",
    gp.GRB.SUBOPTIMAL: "SUBOPTIMAL",
    gp.GRB.INPROGRESS: "INPROGRESS",
    gp.GRB.USER_OBJ_LIMIT: "USER_OBJ_LIMIT"
}

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, sum(capital[i] * values[i] for i in range(6)) - 12.0),
        max(0.0, sum(risk[i] * values[i] for i in range(6)) - 15.0),
        max(0.0, 2.0 - (values[0] + values[1] + values[2])),
        max(0.0, values[0] + values[1] - 1.0)
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal)
else:
    projected_action = [0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None
    objective = None

result = {
    "status": status_names.get(model.Status, "STATUS_" + str(model.Status)),
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
