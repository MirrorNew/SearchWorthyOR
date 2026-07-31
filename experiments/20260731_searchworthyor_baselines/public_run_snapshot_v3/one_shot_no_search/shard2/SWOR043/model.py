import gurobipy as gp
import json
import math

model = gp.Model("SWOR043")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

objective_terms = {
    "x_0": 1010,
    "x_1": 949,
    "x_2": 907,
    "x_3": 846,
    "x_4": 804,
    "x_5": 743
}
model.setObjective(
    gp.quicksum(coef * x[name] for name, coef in objective_terms.items()),
    gp.GRB.MAXIMIZE
)

model.addConstr(gp.quicksum(x[name] for name in names) == 3, name="frozen_assignment_count")
model.addConstr(x["x_0"] + x["x_3"] <= 1, name="subject_1_at_most_one")
model.addConstr(x["x_1"] + x["x_4"] <= 1, name="subject_2_at_most_one")
model.addConstr(x["x_2"] + x["x_5"] <= 1, name="subject_3_at_most_one")
model.addConstr(x["x_0"] + x["x_3"] >= 1, name="core_or_backup_at_least_one")

model.optimize()

status_names = {
    gp.GRB.LOADED: "LOADED",
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.CUTOFF: "CUTOFF",
    gp.GRB.ITERATION_LIMIT: "ITERATION_LIMIT",
    gp.GRB.NODE_LIMIT: "NODE_LIMIT",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.SOLUTION_LIMIT: "SOLUTION_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
    gp.GRB.NUMERIC: "NUMERIC",
    gp.GRB.SUBOPTIMAL: "SUBOPTIMAL",
    gp.GRB.USER_OBJ_LIMIT: "USER_OBJ_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: float(x[name].X) for name in names}
    projected_action = [int(round(values[name])) for name in names]
    objective = float(model.ObjVal)

    rows = [
        ({"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}, "==", 3),
        ({"x_0": 1, "x_3": 1}, "<=", 1),
        ({"x_1": 1, "x_4": 1}, "<=", 1),
        ({"x_2": 1, "x_5": 1}, "<=", 1),
        ({"x_0": 1, "x_3": 1}, ">=", 1)
    ]
    violations = []
    for terms, sense, rhs in rows:
        lhs = sum(coef * values[name] for name, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(values[name] - round(values[name])) for name in names)
else:
    objective = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
