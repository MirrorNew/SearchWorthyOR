import gurobipy as gp
import json

model = gp.Model("SWOR075")
model.Params.OutputFlag = 0

benefit = [1015, 954, 912, 851, 790, 748, 687]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

# code_region: objective.total_network_benefit
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# code_region: constraint.exactly_3_nodes
model.addConstr(gp.quicksum(x) == 3, name="exactly_3_nodes")

# code_region: constraint.service_area_1_coverage
model.addConstr(x[0] + x[2] + x[4] + x[6] >= 1, name="service_area_1_coverage")

# code_region: constraint.service_area_2_coverage
model.addConstr(x[1] + x[3] + x[5] >= 1, name="service_area_2_coverage")

# code_region: constraint.node_A_ineligible
model.addConstr(x[0] == 0, name="node_A_ineligible")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw = [float(v.X) for v in x]
    projected = [int(v >= 0.5) for v in raw]
    constraint_violations = [
        abs(sum(raw) - 3.0),
        max(0.0, 1.0 - (raw[0] + raw[2] + raw[4] + raw[6])),
        max(0.0, 1.0 - (raw[1] + raw[3] + raw[5])),
        abs(raw[0])
    ]
    bound_violation = max(max(0.0, -v, v - 1.0) for v in raw)
    max_constraint_violation = max(constraint_violations + [bound_violation])
    integrality_violation = max(abs(v - round(v)) for v in raw)
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected,
        "max_constraint_violation": float(max_constraint_violation),
        "integrality_violation": float(integrality_violation)
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
