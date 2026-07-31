import gurobipy as gp
import json
import math

model = gp.Model("SWOR012")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
values = [1015, 954, 912, 851, 790, 748]
model.setObjective(gp.quicksum(values[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[1] >= 1, name="emergency_cover")
model.addConstr(x[1] + x[2] >= 1, name="continuity_cover")
model.addConstr(x[0] + x[2] >= 1, name="specialty_cover")
model.addConstr(x[0] + x[3] >= 1, name="core_or_backup")
model.addConstr(x[0] + x[1] <= 1, name="lqg_excludes_180_day_path")
model.addConstr(x[0] - x[4] - x[5] <= 0, name="lqg_requires_90_day_capacity")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))
objective = None
projected_action = []
max_constraint_violation = None
integrality_violation = None
optimal_actions = []

constraint_data = [
    ([1, 1, 1, 1, 1, 1], "==", 3),
    ([1, 1, 0, 0, 0, 0], ">=", 1),
    ([0, 1, 1, 0, 0, 0], ">=", 1),
    ([1, 0, 1, 0, 0, 0], ">=", 1),
    ([1, 0, 0, 1, 0, 0], ">=", 1),
    ([1, 1, 0, 0, 0, 0], "<=", 1),
    ([1, 0, 0, 0, -1, -1], "<=", 0)
]

def violation(lhs, sense, rhs):
    if sense == "<=":
        return max(0.0, lhs - rhs)
    if sense == ">=":
        return max(0.0, rhs - lhs)
    return abs(lhs - rhs)

if model.SolCount > 0:
    raw = [x[i].X for i in range(6)]
    projected_action = [int(v >= 0.5) for v in raw]
    objective = float(model.ObjVal)
    max_constraint_violation = max(
        violation(sum(coeff[i] * raw[i] for i in range(6)), sense, rhs)
        for coeff, sense, rhs in constraint_data
    )
    integrality_violation = max(abs(v - round(v)) for v in raw)

    if model.Status == gp.GRB.OPTIMAL:
        for mask in range(1 << 6):
            candidate = [(mask >> i) & 1 for i in range(6)]
            feasible = all(
                violation(sum(coeff[i] * candidate[i] for i in range(6)), sense, rhs) <= 1e-9
                for coeff, sense, rhs in constraint_data
            )
            candidate_objective = sum(values[i] * candidate[i] for i in range(6))
            if feasible and math.isclose(candidate_objective, objective, rel_tol=0.0, abs_tol=1e-6):
                optimal_actions.append(candidate)

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
    "optimal_actions": optimal_actions
}
print(json.dumps(result, ensure_ascii=False))