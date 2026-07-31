import gurobipy
import json
import math

model = gurobipy.Model("SWOR060")
model.Params.OutputFlag = 0

x = {
    "x_0": model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name="x_0"),
    "x_1": model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name="x_1"),
    "x_2": model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name="x_2"),
    "x_3": model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name="x_3"),
    "x_4": model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name="x_4"),
    "x_5": model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name="x_5"),
    "x_6": model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name="x_6")
}

objective_terms = {
    "x_0": 1011, "x_1": 950, "x_2": 908, "x_3": 847,
    "x_4": 805, "x_5": 744, "x_6": 683
}
model.setObjective(
    gurobipy.quicksum(coef * x[name] for name, coef in objective_terms.items()),
    gurobipy.GRB.MAXIMIZE
)

constraint_specs = [
    ("chain_segment_1_exactly_one", "==", 1, {"x_0": 1, "x_3": 1, "x_6": 1}),
    ("chain_segment_2_exactly_one", "==", 1, {"x_1": 1, "x_4": 1}),
    ("chain_segment_3_exactly_one", "==", 1, {"x_2": 1, "x_5": 1}),
    ("core_backup_emergency_exactly_one", "==", 1, {"x_1": 1, "x_4": 1, "x_6": 1}),
    ("external_safeguard_at_least_one", ">=", 1, {"x_5": 1, "x_6": 1})
]

for name, sense, rhs, terms in constraint_specs:
    lhs = gurobipy.quicksum(coef * x[var_name] for var_name, coef in terms.items())
    if sense == "==":
        model.addConstr(lhs == rhs, name=name)
    elif sense == ">=":
        model.addConstr(lhs >= rhs, name=name)
    else:
        model.addConstr(lhs <= rhs, name=name)

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
    gurobipy.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))
action_projection = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]

if model.SolCount > 0:
    values = {name: x[name].X for name in action_projection}
    projected_action = [int(round(values[name])) for name in action_projection]
    violations = []
    for _, sense, rhs, terms in constraint_specs:
        lhs_value = sum(coef * values[var_name] for var_name, coef in terms.items())
        if sense == "==":
            violations.append(abs(lhs_value - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs_value))
        else:
            violations.append(max(0.0, lhs_value - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values.values())
    objective = model.ObjVal if math.isfinite(model.ObjVal) else None
else:
    objective = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))