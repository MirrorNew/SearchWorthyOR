import gurobipy as gp
import json
import math

model = gp.Model("SWOR006")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

profits = [1018, 957, 896, 854, 793, 751]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="build_exactly_three")
model.addConstr(x[0] + x[2] + x[4] >= 1, name="cover_service_area_1")
model.addConstr(x[1] + x[3] + x[5] >= 1, name="cover_service_area_2")
model.addConstr(x[0] + x[3] >= 1, name="enable_core_or_backup")

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
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    integrality_violation = max(abs(value - round(value)) for value in values)

    violations = []
    for constr in model.getConstrs():
        lhs = sum(model.getCoeff(constr, var) * var.X for var in x)
        if constr.Sense == "<":
            violation = max(0.0, lhs - constr.RHS)
        elif constr.Sense == ">":
            violation = max(0.0, constr.RHS - lhs)
        else:
            violation = abs(lhs - constr.RHS)
        violations.append(violation)

    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations) if violations else 0.0,
        "integrality_violation": integrality_violation
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