import gurobipy as gp
import json

model = gp.Model("SWOR004_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
benefits = [1010, 949, 907, 846, 804, 743, 682]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x[i] for i in range(7)) == 3, name="c_exactly_three")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="c_front_segment_min")
model.addConstr(x[1] + x[2] + x[4] >= 1, name="c_back_segment_min")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="c_core_packages_min")
model.addConstr(x[0] == 0, name="c_evidence_A_ineligible")

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
    values = [x[i].X for i in range(7)]
    projected_action = [int(round(v)) for v in values]
    violations = [
        abs(sum(values) - 3),
        max(0.0, 1 - (values[0] + values[1] + values[3] + values[6])),
        max(0.0, 1 - (values[1] + values[2] + values[4])),
        max(0.0, 2 - (values[0] + values[1] + values[2])),
        abs(values[0])
    ]
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(v - round(v)) for v in values)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0, 0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))