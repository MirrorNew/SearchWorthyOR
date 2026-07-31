import gurobipy as gp
import json
import math

model = gp.Model('SWOR022_patched')
model.Params.OutputFlag = 0

x = model.addVars(6, vtype=gp.GRB.BINARY, lb=0, ub=1, name='x')
profit = [1006, 964, 903, 842, 800, 739]

model.setObjective(gp.quicksum(profit[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x[i] for i in range(6)) == 3, name='choose_exactly_3')
model.addConstr(x[0] + x[1] + x[3] >= 1, name='front_coverage')
model.addConstr(x[1] + x[2] + x[4] >= 1, name='back_coverage')
model.addConstr(x[1] + x[4] + x[5] == 1, name='core_exactly_1')
model.addConstr(x[0] == 0, name='policy_A_ineligible')

model.optimize()
status_names = {
    gp.GRB.OPTIMAL: 'OPTIMAL',
    gp.GRB.INFEASIBLE: 'INFEASIBLE',
    gp.GRB.UNBOUNDED: 'UNBOUNDED',
    gp.GRB.INF_OR_UNBD: 'INF_OR_UNBD'
}
status = status_names.get(model.Status, str(model.Status))

if model.Status == gp.GRB.OPTIMAL:
    raw = [x[i].X for i in range(6)]
    action = [int(round(v)) for v in raw]
    activities = [
        sum(raw),
        raw[0] + raw[1] + raw[3],
        raw[1] + raw[2] + raw[4],
        raw[1] + raw[4] + raw[5],
        raw[0]
    ]
    violations = [
        abs(activities[0] - 3),
        max(0.0, 1 - activities[1]),
        max(0.0, 1 - activities[2]),
        abs(activities[3] - 1),
        abs(activities[4])
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in raw)
    objective = model.ObjVal
else:
    action = [0, 0, 0, 0, 0, 0]
    objective = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    'status': status,
    'objective': objective,
    'projected_action': action,
    'max_constraint_violation': max_constraint_violation,
    'integrality_violation': integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))