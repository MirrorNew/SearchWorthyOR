import gurobipy as gp
import json
import math

m = gp.Model("SWOR017_patched")
m.Params.OutputFlag = 0

semantic_names = ["模式A", "模式B", "模式C", "模式D", "模式E", "模式F", "模式G", "模式H"]
profits = [1005, 963, 902, 841, 799, 738, 696, 635]
capacity = [3, 4, 1, 2, 3, 4, 1, 2]

x = [m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_" + str(i)) for i in range(8)]
m.setObjective(gp.quicksum(profits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

m.addConstr(gp.quicksum(x[i] for i in range(8)) <= 3, name="mode_count_limit")
m.addConstr(gp.quicksum(capacity[i] * x[i] for i in range(8)) <= 8, name="equipment_capacity_limit")
m.addConstr(x[6] + x[7] <= 1, name="backup_modes_mutex")
m.addConstr(x[0] + x[1] <= 1, name="policy_A_excludes_B")

m.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(m.Status, "STATUS_" + str(m.Status))

if m.SolCount > 0:
    raw = [float(v.X) for v in x]
    projected_action = [int(round(value)) for value in raw]
    lhs_count = sum(raw)
    lhs_capacity = sum(capacity[i] * raw[i] for i in range(8))
    lhs_backup = raw[6] + raw[7]
    lhs_policy = raw[0] + raw[1]
    max_constraint_violation = max(
        0.0,
        lhs_count - 3.0,
        lhs_capacity - 8.0,
        lhs_backup - 1.0,
        lhs_policy - 1.0
    )
    integrality_violation = max(min(abs(value), abs(1.0 - value)) for value in raw)
    result = {
        "status": status,
        "objective": float(m.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": float(max_constraint_violation),
        "integrality_violation": float(integrality_violation)
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
