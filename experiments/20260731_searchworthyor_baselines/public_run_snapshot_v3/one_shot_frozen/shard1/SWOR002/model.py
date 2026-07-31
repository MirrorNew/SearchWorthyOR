import gurobipy as gp
import json
import math

model = gp.Model('SWOR002_patched')
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f'x_{i}') for i in range(7)]

objective_coefficients = [1008, 947, 905, 844, 802, 741, 699]
model.setObjective(gp.quicksum(objective_coefficients[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) <= 3, name='module_limit')
model.addConstr(x[0] + x[3] + x[6] >= 1, name='zone_1_connectivity')
model.addConstr(x[1] + x[4] >= 1, name='zone_2_connectivity')
model.addConstr(x[2] + x[5] >= 1, name='zone_3_connectivity')
model.addConstr(x[0] - x[1] - x[4] <= 0, name='A_requires_B_or_E')
model.addConstr(x[5] + x[6] <= 1, name='F_G_mutual_exclusion')
model.addConstr(x[5] + x[6] >= 1, name='applicable_safeguard_requirement')

constraint_specs = [
    ({0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1}, '<=', 3),
    ({0: 1, 3: 1, 6: 1}, '>=', 1),
    ({1: 1, 4: 1}, '>=', 1),
    ({2: 1, 5: 1}, '>=', 1),
    ({0: 1, 1: -1, 4: -1}, '<=', 0),
    ({5: 1, 6: 1}, '<=', 1),
    ({5: 1, 6: 1}, '>=', 1)
]

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: 'OPTIMAL',
    gp.GRB.INFEASIBLE: 'INFEASIBLE',
    gp.GRB.INF_OR_UNBD: 'INF_OR_UNBD',
    gp.GRB.UNBOUNDED: 'UNBOUNDED',
    gp.GRB.TIME_LIMIT: 'TIME_LIMIT'
}
status = status_names.get(model.Status, str(model.Status))
has_solution = model.SolCount > 0
values = [float(var.X) for var in x] if has_solution else [0.0] * 7
projected_action = [int(round(value)) for value in values]

violations = []
for terms, sense, rhs in constraint_specs:
    lhs = sum(coefficient * values[index] for index, coefficient in terms.items())
    if sense == '<=':
        violations.append(max(0.0, lhs - rhs))
    elif sense == '>=':
        violations.append(max(0.0, rhs - lhs))
    else:
        violations.append(abs(lhs - rhs))
for value in values:
    violations.append(max(0.0, -value, value - 1.0))

max_constraint_violation = max(violations) if violations else 0.0
integrality_violation = max(abs(value - round(value)) for value in values) if values else 0.0

result = {
    'status': status,
    'objective': float(model.ObjVal) if has_solution else None,
    'projected_action': projected_action,
    'max_constraint_violation': float(max_constraint_violation),
    'integrality_violation': float(integrality_violation)
}
print(json.dumps(result, ensure_ascii=False))
