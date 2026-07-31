import gurobipy as gp
import json
import math

model = gp.Model("SWOR054_patched")
model.Params.OutputFlag = 0

# REGION: VARIABLES
semantic_names = [
    "匹配A（效用1014；协调资源点2；基础类别）",
    "匹配B（效用953；协调资源点3；基础类别）",
    "匹配C（效用911；协调资源点4；基础类别）",
    "匹配D（效用850；协调资源点1；基础类别）",
    "匹配E（效用789；协调资源点2；基础类别）",
    "匹配F（效用747；协调资源点3；保障类别1）",
    "匹配G（效用686；协调资源点4；保障类别2）"
]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

# REGION: OBJECTIVE
utility = [1014, 953, 911, 850, 789, 747, 686]
model.setObjective(gp.quicksum(utility[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# REGION: C_EXACTLY_THREE
model.addConstr(gp.quicksum(x) == 3, name="base_exactly_three")

# REGION: C_SUBJECT_1
model.addConstr(x[0] + x[3] + x[6] <= 1, name="base_subject_1_at_most_one")

# REGION: C_SUBJECT_2
model.addConstr(x[1] + x[4] <= 1, name="base_subject_2_at_most_one")

# REGION: C_SUBJECT_3
model.addConstr(x[2] + x[5] <= 1, name="base_subject_3_at_most_one")

# REGION: C_BACKUP
model.addConstr(x[5] + x[6] <= 1, name="base_backup_at_most_one")

# REGION: C_POLICY_SAFEGUARD
model.addConstr(x[5] + x[6] >= 1, name="policy_minimum_one_safeguard")

model.optimize()

# REGION: SOLUTION_AND_DIAGNOSTICS
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
    values = [float(v.X) for v in x]
    projected_action = [int(v >= 0.5) for v in values]
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, values[0] + values[3] + values[6] - 1.0),
        max(0.0, values[1] + values[4] - 1.0),
        max(0.0, values[2] + values[5] - 1.0),
        max(0.0, values[5] + values[6] - 1.0),
        max(0.0, 1.0 - values[5] - values[6])
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(min(abs(v), abs(v - 1.0)) for v in values)
    objective = float(model.ObjVal)
else:
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
