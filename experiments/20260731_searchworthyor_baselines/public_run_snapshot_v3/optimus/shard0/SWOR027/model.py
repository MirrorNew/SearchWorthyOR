import gurobipy as gp
import json
import math

model = gp.Model("SWOR027")
model.Params.OutputFlag = 0

benefit = [1008, 947, 905, 844, 802, 741, 699, 638]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="selection_count_exact")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="front_plan_minimum")
model.addConstr(x[1] + x[2] + x[4] + x[7] >= 1, name="back_plan_minimum")
model.addConstr(x[0] + x[3] >= 1, name="core_candidate_minimum")
model.addConstr(x[0] == 0, name="evidence_package_A_ineligible")

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
    values = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in values]
    objective = float(model.ObjVal)

    constraint_specs = [
        ("==", 3.0, {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1}),
        (">=", 1.0, {0: 1, 1: 1, 3: 1, 6: 1}),
        (">=", 1.0, {1: 1, 2: 1, 4: 1, 7: 1}),
        (">=", 1.0, {0: 1, 3: 1}),
        ("==", 0.0, {0: 1})
    ]
    max_constraint_violation = 0.0
    for sense, rhs, terms in constraint_specs:
        lhs = sum(coef * values[index] for index, coef in terms.items())
        if sense == "==":
            violation = math.fabs(lhs - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs)
        else:
            violation = max(0.0, lhs - rhs)
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(math.fabs(v - round(v)) for v in values)
else:
    objective = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
