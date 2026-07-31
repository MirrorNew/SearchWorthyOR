import gurobipy as gp
import json
import math

model = gp.Model('SWOR026_patched')
model.Params.OutputFlag = 0

names = ['x_0', 'x_1', 'x_2', 'x_3', 'x_4', 'x_5', 'x_6']
profit = [1002, 960, 899, 857, 796, 735, 693]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]

model.setObjective(gp.quicksum(profit[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) <= 3, name='base_max_three')
model.addConstr(x[0] + x[3] + x[6] >= 1, name='base_area_1_connectivity')
model.addConstr(x[1] + x[4] >= 1, name='base_area_2_connectivity')
model.addConstr(x[2] + x[5] >= 1, name='base_area_3_connectivity')
model.addConstr(x[0] - x[1] - x[4] <= 0, name='base_A_requires_B_or_E')
model.addConstr(x[1] + x[4] + x[6] == 1, name='base_exactly_one_B_E_G')
model.addConstr(x[0] + x[1] <= 1, name='policy_A_excludes_B')

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: 'OPTIMAL',
    gp.GRB.INFEASIBLE: 'INFEASIBLE',
    gp.GRB.UNBOUNDED: 'UNBOUNDED',
    gp.GRB.INF_OR_UNBD: 'INF_OR_UNBD',
    gp.GRB.TIME_LIMIT: 'TIME_LIMIT'
}
result = {
    'status': status_names.get(model.Status, str(model.Status)),
    'objective': None,
    'projected_action': [],
    'max_constraint_violation': None,
    'integrality_violation': None
}

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected = [int(round(value)) for value in values]
    checks = [
        ('<=', sum(values), 3.0),
        ('>=', values[0] + values[3] + values[6], 1.0),
        ('>=', values[1] + values[4], 1.0),
        ('>=', values[2] + values[5], 1.0),
        ('<=', values[0] - values[1] - values[4], 0.0),
        ('==', values[1] + values[4] + values[6], 1.0),
        ('<=', values[0] + values[1], 1.0)
    ]
    violations = []
    for sense, lhs, rhs in checks:
        if sense == '<=':
            violations.append(max(0.0, lhs - rhs))
        elif sense == '>=':
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    objective = float(model.ObjVal)
    result['objective'] = objective if math.isfinite(objective) else None
    result['projected_action'] = projected
    result['max_constraint_violation'] = max(violations)
    result['integrality_violation'] = max(abs(value - round(value)) for value in values)

print(json.dumps(result, ensure_ascii=False, sort_keys=True))
