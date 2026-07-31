import gurobipy as gp
import json
import math

model = gp.Model("SWOR082_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0
model.Params.Threads = 1
model.Params.Seed = 0

# REGION_VARIABLES
semantic_names = ["路径包A", "路径包B", "路径包C", "路径包D", "路径包E", "路径包F"]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}") for i in range(6)]

# REGION_OBJECTIVE
benefit = [1007, 965, 904, 843, 801, 740]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

# REGION_BASE_SEGMENT_1
model.addConstr(x[0] + x[3] == 1, name="segment_1_exactly_one")
# REGION_BASE_SEGMENT_2
model.addConstr(x[1] + x[4] == 1, name="segment_2_exactly_one")
# REGION_BASE_SEGMENT_3
model.addConstr(x[2] + x[5] == 1, name="segment_3_exactly_one")
# REGION_BASE_BACKUP_EXCLUSION
model.addConstr(x[4] + x[5] <= 1, name="backup_E_F_exclusion")
# REGION_POLICY_AB_EXCLUSION
model.addConstr(x[0] + x[1] <= 1, name="policy_A_B_exclusion")

model.optimize()

# REGION_OUTPUT
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))
has_solution = model.SolCount > 0
values = [float(v.X) for v in x] if has_solution else [0.0] * 6
projected_action = [int(round(value)) for value in values]

rows = [
    ({0: 1.0, 3: 1.0}, "==", 1.0),
    ({1: 1.0, 4: 1.0}, "==", 1.0),
    ({2: 1.0, 5: 1.0}, "==", 1.0),
    ({4: 1.0, 5: 1.0}, "<=", 1.0),
    ({0: 1.0, 1: 1.0}, "<=", 1.0)
]
violations = []
for coefficients, sense, rhs in rows:
    activity = sum(coefficient * values[index] for index, coefficient in coefficients.items())
    if sense == "<=":
        violations.append(max(0.0, activity - rhs))
    elif sense == ">=":
        violations.append(max(0.0, rhs - activity))
    else:
        violations.append(abs(activity - rhs))

max_constraint_violation = max(violations) if violations else 0.0
integrality_violation = max(abs(value - round(value)) for value in values)
objective = float(model.ObjVal) if has_solution and math.isfinite(model.ObjVal) else None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))