import gurobipy as gp
import json
import math

model = gp.Model("SWOR076_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

utilities = [1010, 949, 907, 846, 804, 743, 682, 640]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
model.update()

model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="required_enabled_units")
model.addConstr(x[0] + x[1] >= 1, name="emergency_coverage")
model.addConstr(x[1] + x[2] >= 1, name="continuity_coverage")
model.addConstr(x[0] + x[2] >= 1, name="specialty_coverage")
model.addConstr(x[6] + x[7] <= 1, name="terminal_backup_exclusion")
model.addConstr(x[0] + x[1] <= 1, name="applicable_policy_A_excludes_B")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": None,
    "projected_action": [],
    "max_constraint_violation": None,
    "integrality_violation": None
}

if model.SolCount > 0:
    raw = [x[i].X for i in range(8)]
    projected = [int(round(value)) for value in raw]
    evaluations = [
        (sum(raw), "==", 3.0),
        (raw[0] + raw[1], ">=", 1.0),
        (raw[1] + raw[2], ">=", 1.0),
        (raw[0] + raw[2], ">=", 1.0),
        (raw[6] + raw[7], "<=", 1.0),
        (raw[0] + raw[1], "<=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in evaluations:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    result["objective"] = float(model.ObjVal)
    result["projected_action"] = projected
    result["max_constraint_violation"] = float(max(violations))
    result["integrality_violation"] = float(max(abs(value - round(value)) for value in raw))

print(json.dumps(result, ensure_ascii=False))