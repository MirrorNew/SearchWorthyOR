import gurobipy
import json
import math

PATCHED_IR = {
    'model_id': 'SWOR030_patched',
    'world': 'policy_patched',
    'sense': 'max',
    'single_objective': True,
    'variables': [
        {'name': 'x_0', 'vartype': 'B', 'lb': 0, 'ub': 1, 'semantic_name': '模式A是否启用'},
        {'name': 'x_1', 'vartype': 'B', 'lb': 0, 'ub': 1, 'semantic_name': '模式B是否启用'},
        {'name': 'x_2', 'vartype': 'B', 'lb': 0, 'ub': 1, 'semantic_name': '模式C是否启用'},
        {'name': 'x_3', 'vartype': 'B', 'lb': 0, 'ub': 1, 'semantic_name': '模式D是否启用'},
        {'name': 'x_4', 'vartype': 'B', 'lb': 0, 'ub': 1, 'semantic_name': '模式E是否启用'},
        {'name': 'x_5', 'vartype': 'B', 'lb': 0, 'ub': 1, 'semantic_name': '模式F是否启用'}
    ],
    'objective': {
        'constant': 0,
        'terms': {'x_0': 1003, 'x_1': 961, 'x_2': 900, 'x_3': 858, 'x_4': 797, 'x_5': 736}
    },
    'constraints': [
        {'name': 'maximum_enabled_modes', 'sense': '<=', 'rhs': 3, 'terms': {'x_0': 1, 'x_1': 1, 'x_2': 1, 'x_3': 1, 'x_4': 1, 'x_5': 1}},
        {'name': 'equipment_capacity', 'sense': '<=', 'rhs': 9, 'terms': {'x_0': 2, 'x_1': 3, 'x_2': 4, 'x_3': 1, 'x_4': 2, 'x_5': 3}},
        {'name': 'minimum_enabled_core_modes', 'sense': '>=', 'rhs': 2, 'terms': {'x_0': 1, 'x_1': 1, 'x_2': 1}},
        {'name': 'policy_A_B_incompatibility', 'sense': '<=', 'rhs': 1, 'terms': {'x_0': 1, 'x_1': 1}}
    ],
    'action_projection': ['x_0', 'x_1', 'x_2', 'x_3', 'x_4', 'x_5']
}

model = gurobipy.Model(PATCHED_IR['model_id'])
model.Params.OutputFlag = 0
variables = {}
for specification in PATCHED_IR['variables']:
    variables[specification['name']] = model.addVar(
        lb=specification['lb'],
        ub=specification['ub'],
        vtype=gurobipy.GRB.BINARY,
        name=specification['name']
    )

objective = PATCHED_IR['objective']['constant'] + gurobipy.quicksum(
    coefficient * variables[name]
    for name, coefficient in PATCHED_IR['objective']['terms'].items()
)
model.setObjective(objective, gurobipy.GRB.MAXIMIZE)

for constraint in PATCHED_IR['constraints']:
    lhs = gurobipy.quicksum(
        coefficient * variables[name]
        for name, coefficient in constraint['terms'].items()
    )
    if constraint['sense'] == '<=':
        model.addConstr(lhs <= constraint['rhs'], name=constraint['name'])
    elif constraint['sense'] == '>=':
        model.addConstr(lhs >= constraint['rhs'], name=constraint['name'])
    elif constraint['sense'] == '==':
        model.addConstr(lhs == constraint['rhs'], name=constraint['name'])
    else:
        raise ValueError('Unsupported constraint sense')

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: 'OPTIMAL',
    gurobipy.GRB.INFEASIBLE: 'INFEASIBLE',
    gurobipy.GRB.INF_OR_UNBD: 'INF_OR_UNBD',
    gurobipy.GRB.UNBOUNDED: 'UNBOUNDED',
    gurobipy.GRB.TIME_LIMIT: 'TIME_LIMIT',
    gurobipy.GRB.INTERRUPTED: 'INTERRUPTED'
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    projected_action = [int(round(variables[name].X)) for name in PATCHED_IR['action_projection']]
    objective_value = float(model.ObjVal)
    max_constraint_violation = 0.0
    for constraint in PATCHED_IR['constraints']:
        lhs_value = sum(
            coefficient * variables[name].X
            for name, coefficient in constraint['terms'].items()
        )
        if constraint['sense'] == '<=':
            violation = max(0.0, lhs_value - constraint['rhs'])
        elif constraint['sense'] == '>=':
            violation = max(0.0, constraint['rhs'] - lhs_value)
        else:
            violation = math.fabs(lhs_value - constraint['rhs'])
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(
        math.fabs(variables[name].X - round(variables[name].X))
        for name in PATCHED_IR['action_projection']
    )
else:
    projected_action = [0 for name in PATCHED_IR['action_projection']]
    objective_value = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    'status': status,
    'objective': objective_value,
    'projected_action': projected_action,
    'max_constraint_violation': max_constraint_violation,
    'integrality_violation': integrality_violation
}
print(json.dumps(result, ensure_ascii=False))