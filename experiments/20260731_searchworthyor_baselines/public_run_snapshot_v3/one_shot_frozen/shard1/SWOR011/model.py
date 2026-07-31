import gurobipy
import json
import math

model = gurobipy.Model("SWOR011_patched")
model.Params.OutputFlag = 0

x = [
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name="x_0"),
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name="x_1"),
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name="x_2"),
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name="x_3"),
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name="x_4"),
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name="x_5"),
]

model.setObjective(
    1016 * x[0] + 955 * x[1] + 894 * x[2]
    + 852 * x[3] + 791 * x[4] + 749 * x[5],
    gurobipy.GRB.MAXIMIZE,
)

model.addConstr(sum(x) == 3, name="required_assignments_3")
model.addConstr(x[0] + x[3] <= 1, name="subject_1_A_D_cap")
model.addConstr(x[1] + x[4] <= 1, name="subject_2_B_E_cap")
model.addConstr(x[2] + x[5] <= 1, name="subject_3_C_F_cap")
model.addConstr(x[0] == 0, name="policy_match_A_ineligible")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, values[0] + values[3] - 1.0),
        max(0.0, values[1] + values[4] - 1.0),
        max(0.0, values[2] + values[5] - 1.0),
        abs(values[0]),
    ]
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    projected_action = [0, 0, 0, 0, 0, 0]
    objective = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))