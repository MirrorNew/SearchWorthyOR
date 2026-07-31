import gurobipy as gp
import json
import math

# [DATA] 候选顺序为A、B、C、D、E、F、G、H。
# 关键工时点分别为3、4、1、2、3、4、1、2；题面未提供总容量。
model = gp.Model("SWOR014_patched")
model.Params.OutputFlag = 0

# [VARIABLES]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

# [OBJECTIVE]
values = [1010, 949, 907, 846, 804, 743, 682, 640]
model.setObjective(gp.quicksum(values[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

# [BASE-C1]
model.addConstr(gp.quicksum(x) == 3, name="base_select_exactly_3")
# [BASE-C2]
model.addConstr(x[0] + x[3] + x[6] >= 1, name="base_period_1_coverage")
# [BASE-C3]
model.addConstr(x[1] + x[4] + x[7] >= 1, name="base_period_2_coverage")
# [BASE-C4]
model.addConstr(x[2] + x[5] >= 1, name="base_period_3_coverage")
# [BASE-C5]
model.addConstr(x[1] + x[4] + x[7] == 1, name="base_core_backup_emergency_exactly_one")
# [PATCH-P1: DOC-E8A042AC76470C76]
model.addConstr(x[0] == 0, name="policy_shift_A_ineligible")

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
    raw = [var.X for var in x]
    projected_action = [int(round(value)) for value in raw]
    integrality_violation = max(abs(value - round(value)) for value in raw)
    lhs_values = [
        sum(raw),
        raw[0] + raw[3] + raw[6],
        raw[1] + raw[4] + raw[7],
        raw[2] + raw[5],
        raw[1] + raw[4] + raw[7],
        raw[0]
    ]
    violations = [
        abs(lhs_values[0] - 3),
        max(0.0, 1 - lhs_values[1]),
        max(0.0, 1 - lhs_values[2]),
        max(0.0, 1 - lhs_values[3]),
        abs(lhs_values[4] - 1),
        abs(lhs_values[5])
    ]
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0, 0, 0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))
