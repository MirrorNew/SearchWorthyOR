import gurobipy
import json
import math

# VARIABLES
model = gurobipy.Model("SWOR099_patched")
model.Params.OutputFlag = 0
x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name="x_" + str(i)) for i in range(8)]

# OBJECTIVE
benefit = [1015, 954, 912, 851, 790, 748, 687, 645]
model.setObjective(gurobipy.quicksum(benefit[i] * x[i] for i in range(8)), gurobipy.GRB.MAXIMIZE)

# BASE_CONSTRAINTS
model.addConstr(gurobipy.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="front_arrival")
model.addConstr(x[1] + x[2] + x[4] + x[7] >= 1, name="back_arrival")
model.addConstr(x[1] + x[4] + x[7] == 1, name="exclusive_B_E_H")

# EVIDENCE_PATCH_DOC_A5F33889CED21786
model.addConstr(x[6] + x[7] >= 1, name="fruit_or_vegetable")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))
result = {
    "status": status,
    "objective": None,
    "projected_action": [],
    "max_constraint_violation": None,
    "integrality_violation": None
}

if model.SolCount > 0:
    raw = [x[i].X for i in range(8)]
    projected = [int(round(value)) for value in raw]
    specs = [
        ([(i, 1.0) for i in range(8)], "==", 3.0),
        ([(0, 1.0), (1, 1.0), (3, 1.0), (6, 1.0)], ">=", 1.0),
        ([(1, 1.0), (2, 1.0), (4, 1.0), (7, 1.0)], ">=", 1.0),
        ([(1, 1.0), (4, 1.0), (7, 1.0)], "==", 1.0),
        ([(6, 1.0), (7, 1.0)], ">=", 1.0)
    ]
    violations = []
    for terms, sense, rhs in specs:
        lhs = sum(coef * raw[index] for index, coef in terms)
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(value - round(value)) for value in raw),
        "selected_packages": [chr(65 + i) for i, value in enumerate(projected) if value == 1]
    }

print(json.dumps(result, ensure_ascii=False))