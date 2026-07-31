import gurobipy as gp
import json
import math

m = gp.Model("SWOR077_patched")
m.Params.OutputFlag = 0

x = [m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
utilities = [1004, 962, 901, 859, 798, 737, 695, 634]
m.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

m.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
m.addConstr(x[0] + x[1] >= 1, name="emergency_coverage_A_B")
m.addConstr(x[1] + x[2] >= 1, name="continuous_care_B_C")
m.addConstr(x[0] + x[2] >= 1, name="specialty_coverage_A_C")
m.addConstr(x[1] + x[4] + x[7] == 1, name="exclusive_B_E_H")
m.addConstr(x[0] == 0, name="policy_A_ineligible")

m.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(m.Status, str(m.Status))

if m.SolCount > 0:
    values = [x[i].X for i in range(8)]
    projected_action = [int(round(v)) for v in values]
    constraint_specs = [
        ({0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1}, "==", 3),
        ({0: 1, 1: 1}, ">=", 1),
        ({1: 1, 2: 1}, ">=", 1),
        ({0: 1, 2: 1}, ">=", 1),
        ({1: 1, 4: 1, 7: 1}, "==", 1),
        ({0: 1}, "==", 0)
    ]
    violations = []
    for terms, sense, rhs in constraint_specs:
        lhs = sum(coef * values[index] for index, coef in terms.items())
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    bound_violations = [max(0.0, -v, v - 1.0) for v in values]
    max_constraint_violation = max(violations + bound_violations)
    integrality_violation = max(abs(v - round(v)) for v in values)
    objective = m.ObjVal
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