import gurobipy as gp
import json
import math

model = gp.Model("SWOR097_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

utilities = [1012, 951, 909, 848, 806, 745, 684, 642]
semantic_names = ["匹配A", "匹配B", "匹配C", "匹配D", "匹配E", "匹配F", "匹配G", "匹配H"]
x = [
    model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}")
    for i in range(8)
]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

constraint_specs = [
    ("assignment_count_eq", "==", 3.0, {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0, 7: 1.0}),
    ("resource_subject_1_cap", "<=", 1.0, {0: 1.0, 3: 1.0, 6: 1.0}),
    ("resource_subject_2_cap", "<=", 1.0, {1: 1.0, 4: 1.0, 7: 1.0}),
    ("resource_subject_3_cap", "<=", 1.0, {2: 1.0, 5: 1.0}),
    ("core_match_min", ">=", 2.0, {0: 1.0, 1: 1.0, 2: 1.0}),
    ("policy_conflict_A_B", "<=", 1.0, {0: 1.0, 1: 1.0})
]

for name, sense, rhs, terms in constraint_specs:
    expression = gp.quicksum(coefficient * x[index] for index, coefficient in terms.items())
    if sense == "<=":
        model.addConstr(expression <= rhs, name=name)
    elif sense == ">=":
        model.addConstr(expression >= rhs, name=name)
    else:
        model.addConstr(expression == rhs, name=name)

model.optimize()
status = "OPTIMAL" if model.Status == gp.GRB.OPTIMAL else str(model.Status)

if model.SolCount > 0:
    values = [variable.X for variable in x]
    projected_action = [int(round(value)) for value in values]
    violations = []
    for value in values:
        violations.append(max(0.0, -value))
        violations.append(max(0.0, value - 1.0))
    for name, sense, rhs, terms in constraint_specs:
        lhs = math.fsum(coefficient * values[index] for index, coefficient in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
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
        "projected_action": [0, 0, 0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))
