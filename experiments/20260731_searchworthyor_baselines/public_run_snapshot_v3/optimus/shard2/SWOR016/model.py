import gurobipy
import json
import math

model = gurobipy.Model("SWOR016_patched")
model.Params.OutputFlag = 0

benefits = [1007, 965, 904, 843, 801, 740, 698, 637]
semantic_names = ["节点A", "节点B", "节点C", "节点D", "节点E", "节点F", "节点G", "节点H"]
x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
model.setObjective(gurobipy.quicksum(benefits[i] * x[i] for i in range(8)), gurobipy.GRB.MAXIMIZE)

model.addConstr(gurobipy.quicksum(x) == 3, name="required_facility_count")
model.addConstr(x[0] + x[2] + x[4] + x[6] >= 1, name="service_area_1_coverage")
model.addConstr(x[1] + x[3] + x[5] + x[7] >= 1, name="service_area_2_coverage")
model.addConstr(x[1] + x[4] + x[7] == 1, name="exclusive_choice_B_E_H")
model.addConstr(x[0] + x[1] <= 1, name="policy_A_excludes_B")

model.optimize()

result = {
    "status": int(model.Status),
    "objective": None,
    "projected_action": [],
    "max_constraint_violation": None,
    "integrality_violation": None
}

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected = [int(round(value)) for value in values]
    lhs_values = [
        sum(values),
        values[0] + values[2] + values[4] + values[6],
        values[1] + values[3] + values[5] + values[7],
        values[1] + values[4] + values[7],
        values[0] + values[1]
    ]
    violations = [
        abs(lhs_values[0] - 3),
        max(0.0, 1 - lhs_values[1]),
        max(0.0, 1 - lhs_values[2]),
        abs(lhs_values[3] - 1),
        max(0.0, lhs_values[4] - 1)
    ]
    result["objective"] = float(model.ObjVal)
    result["projected_action"] = projected
    result["max_constraint_violation"] = float(max(violations))
    result["integrality_violation"] = float(max(abs(value - round(value)) for value in values))

print(json.dumps(result, ensure_ascii=False))