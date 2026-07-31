import gurobipy as gp
import json
import math

model = gp.Model("SWOR083_patched")
model.Params.OutputFlag = 0

x = model.addVars(7, vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name="x")
benefit = [1012, 951, 909, 848, 806, 745, 684]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x[i] for i in range(7)) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="period_1_coverage")
model.addConstr(x[1] + x[4] >= 1, name="period_2_coverage")
model.addConstr(x[2] + x[5] >= 1, name="period_3_coverage")
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_D")
model.addConstr(x[0] + x[1] <= 1, name="external_A_B_mutex")

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
    values = [float(x[i].X) for i in range(7)]
    projected_action = [1 if value >= 0.5 else 0 for value in values]
    objective = float(model.ObjVal)

    specifications = [
        ({0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1}, "==", 3),
        ({0: 1, 3: 1, 6: 1}, ">=", 1),
        ({1: 1, 4: 1}, ">=", 1),
        ({2: 1, 5: 1}, ">=", 1),
        ({0: 1, 3: 1}, ">=", 1),
        ({0: 1, 1: 1}, "<=", 1)
    ]
    violations = []
    for terms, sense, rhs in specifications:
        lhs = sum(coefficient * values[index] for index, coefficient in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = float(max(violations))
    integrality_violation = float(max(min(abs(value - math.floor(value)), abs(math.ceil(value) - value)) for value in values))
else:
    objective = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False, sort_keys=True))