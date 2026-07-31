import gurobipy as gp
import json
import math

model = gp.Model("SWOR082_patched")
model.Params.OutputFlag = 0

# REGION variables_and_objective
semantic_names = ["路径包A", "路径包B", "路径包C", "路径包D", "路径包E", "路径包F"]
profits = [1007, 965, 904, 843, 801, 740]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

# REGION base_constraints
model.addConstr(x[0] + x[3] == 1, name="c_segment_1_exactly_one")
model.addConstr(x[1] + x[4] == 1, name="c_segment_2_exactly_one")
model.addConstr(x[2] + x[5] == 1, name="c_segment_3_exactly_one")
model.addConstr(x[4] + x[5] <= 1, name="c_terminal_reserves_conflict")

# REGION policy_constraint_DOC_EF738A44A6A5653F
model.addConstr(x[0] + x[1] <= 1, name="c_policy_no_A_B")

# REGION solve_and_report
model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)
    violations = [
        abs(values[0] + values[3] - 1.0),
        abs(values[1] + values[4] - 1.0),
        abs(values[2] + values[5] - 1.0),
        max(0.0, values[4] + values[5] - 1.0),
        max(0.0, values[0] + values[1] - 1.0)
    ]
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
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
