import gurobipy as gp
import json

model = gp.Model("SWOR008_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

benefits = [1016, 955, 894, 852, 791, 749, 688]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[2] + x[4] + x[6] >= 1, name="service_area_1_coverage")
model.addConstr(x[1] + x[3] + x[5] >= 1, name="service_area_2_coverage")
model.addConstr(x[1] + x[4] + x[6] == 1, name="B_E_G_exactly_one")
model.addConstr(x[0] + x[1] <= 1, name="CHDV_2010_diesel_disposition_conflict")

constraint_specs = [
    ({0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1}, "==", 3),
    ({0: 1, 2: 1, 4: 1, 6: 1}, ">=", 1),
    ({1: 1, 3: 1, 5: 1}, ">=", 1),
    ({1: 1, 4: 1, 6: 1}, "==", 1),
    ({0: 1, 1: 1}, "<=", 1)
]

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
    raw = [x[i].X for i in range(7)]
    projected_action = [int(round(value)) for value in raw]
    violations = []
    for coefficients, sense, rhs in constraint_specs:
        lhs = sum(coefficient * raw[index] for index, coefficient in coefficients.items())
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(value - round(value)) for value in raw)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0, 0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))