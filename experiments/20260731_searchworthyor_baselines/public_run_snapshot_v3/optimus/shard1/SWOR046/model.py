import gurobipy as gp
import json

model = gp.Model("SWOR046_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

returns = [1007, 965, 904, 843, 801, 740, 698]
capital = [3, 4, 1, 2, 3, 4, 1]
risk = [3, 5, 2, 4, 1, 3, 5]

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
model.setObjective(gp.quicksum(returns[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="position_count")
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(7)) <= 12, name="capital_capacity")
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(7)) <= 15, name="risk_capacity")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="minimum_core_selections")
model.addConstr(x[0] + x[1] <= 1, name="policy_A_implies_not_B")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
has_solution = model.SolCount > 0
raw = [float(var.X) for var in x] if has_solution else [0.0] * 7
projected = [int(round(value)) for value in raw]

def violation(lhs, sense, rhs):
    if sense == "<=":
        return max(0.0, lhs - rhs)
    if sense == ">=":
        return max(0.0, rhs - lhs)
    return abs(lhs - rhs)

constraint_checks = [
    (sum(raw), "==", 3.0),
    (sum(capital[i] * raw[i] for i in range(7)), "<=", 12.0),
    (sum(risk[i] * raw[i] for i in range(7)), "<=", 15.0),
    (raw[0] + raw[1] + raw[2], ">=", 2.0),
    (raw[0] + raw[1], "<=", 1.0)
]
max_constraint_violation = max(violation(lhs, sense, rhs) for lhs, sense, rhs in constraint_checks)
integrality_violation = max(min(abs(value), abs(value - 1.0)) for value in raw)

result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": float(model.ObjVal) if has_solution else None,
    "projected_action": projected,
    "max_constraint_violation": float(max_constraint_violation),
    "integrality_violation": float(integrality_violation)
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
