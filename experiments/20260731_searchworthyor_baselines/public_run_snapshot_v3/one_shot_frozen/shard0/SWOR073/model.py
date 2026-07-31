import gurobipy as gp
import json
import math

model = gp.Model("SWOR073_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]
utilities = [1004, 962, 901, 859, 798, 737]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="base_exactly_3")
model.addConstr(x[0] + x[3] <= 1, name="base_subject1_A_D")
model.addConstr(x[1] + x[4] <= 1, name="base_subject2_B_E")
model.addConstr(x[2] + x[5] <= 1, name="base_subject3_C_F")
model.addConstr(x[4] + x[5] <= 1, name="base_terminal_E_F")
model.addConstr(x[0] + x[1] <= 1, name="policy_A_B_mutex")

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
    raw = [v.X for v in x]
    projected = [int(round(value)) for value in raw]
    lhs_values = [
        sum(raw),
        raw[0] + raw[3],
        raw[1] + raw[4],
        raw[2] + raw[5],
        raw[4] + raw[5],
        raw[0] + raw[1]
    ]
    violations = [
        abs(lhs_values[0] - 3),
        max(0.0, lhs_values[1] - 1),
        max(0.0, lhs_values[2] - 1),
        max(0.0, lhs_values[3] - 1),
        max(0.0, lhs_values[4] - 1),
        max(0.0, lhs_values[5] - 1)
    ]
    bound_violations = [max(0.0, -value, value - 1.0) for value in raw]
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected,
        "max_constraint_violation": float(max(violations + bound_violations)),
        "integrality_violation": float(max(abs(value - round(value)) for value in raw))
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))