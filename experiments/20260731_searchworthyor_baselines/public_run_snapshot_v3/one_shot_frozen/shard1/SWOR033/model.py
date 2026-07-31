import gurobipy as gp
import json
import math

model = gp.Model("SWOR033_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
model.update()

values = [1013, 952, 910, 849, 788, 746]
model.setObjective(gp.quicksum(values[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) <= 3, name="frozen_max_units")
model.addConstr(x[0] + 2*x[1] + 3*x[2] + 4*x[3] + x[4] + 2*x[5] <= 6, name="capacity_limit")
model.addConstr(x[0] + x[3] >= 1, name="clean_capability_min")
model.addConstr(x[1] + x[4] >= 1, name="backup_capability_min")
model.addConstr(x[0] + x[1] <= 1, name="policy_A_excludes_B")

model.optimize()

status_map = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_map.get(model.Status, str(model.Status))

if model.SolCount > 0:
    action = [int(round(v.X)) for v in x]
    checks = [
        (sum(action), "<=", 3.0),
        (action[0] + 2*action[1] + 3*action[2] + 4*action[3] + action[4] + 2*action[5], "<=", 6.0),
        (action[0] + action[3], ">=", 1.0),
        (action[1] + action[4], ">=", 1.0),
        (action[0] + action[1], "<=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": action,
        "max_constraint_violation": max([0.0] + violations),
        "integrality_violation": max(abs(v.X - round(v.X)) for v in x)
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