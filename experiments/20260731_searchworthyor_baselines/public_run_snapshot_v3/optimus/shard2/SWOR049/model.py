import gurobipy as gp
import json

model = gp.Model("SWOR049_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

# OBJECTIVE
returns = [1003, 961, 900, 858, 797, 736]
model.setObjective(gp.quicksum(returns[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

# BASE_REQUIRED_POSITION_COUNT
model.addConstr(gp.quicksum(x) == 3, name="required_position_count")

# BASE_CAPITAL_CAPACITY
capital = [1, 2, 3, 4, 1, 2]
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(6)) <= 12, name="capital_capacity")

# BASE_RISK_CAPACITY
risk = [5, 2, 4, 1, 3, 5]
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(6)) <= 15, name="risk_capacity")

# BASE_EXACT_ONE_B_E_F
model.addConstr(x[1] + x[4] + x[5] == 1, name="exact_one_B_E_F")

# POLICY_DOC_CB71B08E2DBBEF42
model.addConstr(x[0] + x[1] <= 1, name="policy_A_trigger_forbids_B")

model.optimize()

# RESULT_EXTRACTION
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw = [v.X for v in x]
    projected_action = [int(round(value)) for value in raw]
    objective = float(model.ObjVal)

    lhs_values = [
        sum(raw),
        sum(capital[i] * raw[i] for i in range(6)),
        sum(risk[i] * raw[i] for i in range(6)),
        raw[1] + raw[4] + raw[5],
        raw[0] + raw[1]
    ]
    violations = [
        abs(lhs_values[0] - 3),
        max(0.0, lhs_values[1] - 12),
        max(0.0, lhs_values[2] - 15),
        abs(lhs_values[3] - 1),
        max(0.0, lhs_values[4] - 1)
    ]
    max_constraint_violation = float(max(violations))
    integrality_violation = float(max(abs(value - round(value)) for value in raw))
else:
    objective = None
    projected_action = [0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
