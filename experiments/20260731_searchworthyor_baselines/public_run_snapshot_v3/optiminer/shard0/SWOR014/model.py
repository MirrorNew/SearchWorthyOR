import gurobipy as gp
import json

m = gp.Model("SWOR014_patched")
m.Params.OutputFlag = 0

# REGION VARIABLES
x = [m.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}") for i in range(8)]

# REGION OBJECTIVE
benefit = [1010, 949, 907, 846, 804, 743, 682, 640]
m.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

# REGION C_SELECT_EXACTLY_3
m.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")

# REGION C_COVER_PERIOD_1
m.addConstr(x[0] + x[3] + x[6] >= 1, name="cover_period_1")

# REGION C_COVER_PERIOD_2
m.addConstr(x[1] + x[4] + x[7] >= 1, name="cover_period_2")

# REGION C_COVER_PERIOD_3
m.addConstr(x[2] + x[5] >= 1, name="cover_period_3")

# REGION C_EXACTLY_ONE_B_E_H
m.addConstr(x[1] + x[4] + x[7] == 1, name="exactly_one_B_E_H")

# REGION C_POLICY_A_INELIGIBLE
m.addConstr(x[0] == 0, name="policy_A_ineligible")

# REGION SOLVE_AND_REPORT
m.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(m.Status, str(m.Status))

constraint_specs = [
    ("==", 3.0, {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1}),
    (">=", 1.0, {0: 1, 3: 1, 6: 1}),
    (">=", 1.0, {1: 1, 4: 1, 7: 1}),
    (">=", 1.0, {2: 1, 5: 1}),
    ("==", 1.0, {1: 1, 4: 1, 7: 1}),
    ("==", 0.0, {0: 1})
]

if m.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in values]
    violations = []
    for sense, rhs, terms in constraint_specs:
        lhs = sum(coef * values[i] for i, coef in terms.items())
        if sense == "<=":
            violation = max(0.0, lhs - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs)
        else:
            violation = abs(lhs - rhs)
        violations.append(violation)
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(v - round(v)) for v in values)
    objective = float(m.ObjVal)
else:
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None
    objective = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))
