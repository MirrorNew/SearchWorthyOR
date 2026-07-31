import gurobipy as gp
import json

model = gp.Model("SWOR038_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
benefit = [1011, 950, 908, 847, 805, 744]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) <= 3, name="max_three_modules")
model.addConstr(x[0] + x[3] >= 1, name="zone_1_connectivity")
model.addConstr(x[1] + x[4] >= 1, name="zone_2_connectivity")
model.addConstr(x[2] + x[5] >= 1, name="zone_3_connectivity")
model.addConstr(x[0] - x[1] - x[4] <= 0, name="A_requires_B_or_E")
model.addConstr(x[1] + x[4] + x[5] == 1, name="exactly_one_B_E_F")
# POLICY_MEAL_COVERAGE_A: DOC-D5BB9462982449FA
model.addConstr(x[0] - x[4] - x[5] <= 0, name="policy_meal_coverage_A")

model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}

if model.SolCount > 0:
    raw = [v.X for v in x]
    projected = [int(round(value)) for value in raw]
    violations = [
        max(0.0, sum(raw) - 3.0),
        max(0.0, 1.0 - raw[0] - raw[3]),
        max(0.0, 1.0 - raw[1] - raw[4]),
        max(0.0, 1.0 - raw[2] - raw[5]),
        max(0.0, raw[0] - raw[1] - raw[4]),
        abs(raw[1] + raw[4] + raw[5] - 1.0),
        max(0.0, raw[0] - raw[4] - raw[5])
    ]
    result = {
        "status": status_names.get(model.Status, str(model.Status)),
        "objective": float(model.ObjVal),
        "projected_action": projected,
        "max_constraint_violation": float(max(violations)),
        "integrality_violation": float(max(abs(value - round(value)) for value in raw))
    }
else:
    result = {
        "status": status_names.get(model.Status, str(model.Status)),
        "objective": None,
        "projected_action": [0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))