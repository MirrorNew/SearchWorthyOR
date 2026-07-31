import gurobipy as gp
import json

model = gp.Model("SWOR051")
model.Params.OutputFlag = 0

# [V01-V06] Binary module decisions in action-projection order
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

# [O01] Single service-coverage objective
benefit = [1004, 962, 901, 859, 798, 737]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

# [C01] At most three enabled modules
model.addConstr(gp.quicksum(x) <= 3, name="module_limit")
# [C02] Communication zone 1 connectivity
model.addConstr(x[0] + x[3] >= 1, name="zone1_connectivity")
# [C03] Communication zone 2 connectivity
model.addConstr(x[1] + x[4] >= 1, name="zone2_connectivity")
# [C04] Communication zone 3 connectivity
model.addConstr(x[2] + x[5] >= 1, name="zone3_connectivity")
# [C05] Module A requires module B or E
model.addConstr(-x[0] + x[1] + x[4] >= 0, name="module_a_requires_backhaul")
# [C06] First core candidate A or backup D
model.addConstr(x[0] + x[3] >= 1, name="core_candidate_or_backup")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [v.X for v in x]
    projected_action = [int(value >= 0.5) for value in values]
    lhs_values = [
        sum(values),
        values[0] + values[3],
        values[1] + values[4],
        values[2] + values[5],
        -values[0] + values[1] + values[4],
        values[0] + values[3]
    ]
    violations = [
        max(0.0, lhs_values[0] - 3.0),
        max(0.0, 1.0 - lhs_values[1]),
        max(0.0, 1.0 - lhs_values[2]),
        max(0.0, 1.0 - lhs_values[3]),
        max(0.0, 0.0 - lhs_values[4]),
        max(0.0, 1.0 - lhs_values[5])
    ]
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(value - round(value)) for value in values)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))