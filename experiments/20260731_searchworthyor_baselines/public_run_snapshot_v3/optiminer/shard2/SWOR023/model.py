import gurobipy as gp
import json
import math

m = gp.Model("SWOR023")
m.Params.OutputFlag = 0

x = [m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

utilities = [1012, 951, 909, 848, 806, 745, 684]
m.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

m.addConstr(gp.quicksum(x) == 3, name="exactly_three_units")
m.addConstr(x[0] + x[1] >= 1, name="emergency_coverage")
m.addConstr(x[1] + x[2] >= 1, name="continuity_coverage")
m.addConstr(x[0] + x[2] >= 1, name="specialty_coverage")
m.addConstr(x[0] == 0, name="policy_A_ineligible")

m.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(m.Status, str(m.Status))

if m.SolCount > 0:
    values = [v.X for v in x]
    projected_action = [int(value >= 0.5) for value in values]
    lhs_values = [
        sum(values),
        values[0] + values[1],
        values[1] + values[2],
        values[0] + values[2],
        values[0]
    ]
    senses = ["==", ">=", ">=", ">=", "=="]
    rhs_values = [3, 1, 1, 1, 0]
    violations = []
    for lhs, sense, rhs in zip(lhs_values, senses, rhs_values):
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    result = {
        "status": status,
        "objective": m.ObjVal,
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

print(json.dumps(result, ensure_ascii=False))