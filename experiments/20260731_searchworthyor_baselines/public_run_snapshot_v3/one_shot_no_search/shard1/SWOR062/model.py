import gurobipy as gp
import json
import math

model = gp.Model('SWOR062')
model.Params.OutputFlag = 0

# region variables
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f'x_{i}') for i in range(8)]
# endregion variables

# region objective
benefits = [1016, 955, 894, 852, 791, 749, 688, 646]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)
# endregion objective

# region max_units
model.addConstr(gp.quicksum(x) <= 3, name='max_units')
# endregion max_units

# region grid_capacity
capacity = [1, 2, 3, 4, 1, 2, 3, 4]
model.addConstr(gp.quicksum(capacity[i] * x[i] for i in range(8)) <= 6, name='grid_capacity')
# endregion grid_capacity

# region clean_capacity
model.addConstr(x[0] + x[3] + x[6] >= 1, name='clean_capacity')
# endregion clean_capacity

# region backup_capacity
model.addConstr(x[1] + x[4] + x[7] >= 1, name='backup_capacity')
# endregion backup_capacity

# region core_or_backup
model.addConstr(x[0] + x[3] >= 1, name='core_or_backup')
# endregion core_or_backup

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: 'OPTIMAL',
    gp.GRB.INFEASIBLE: 'INFEASIBLE',
    gp.GRB.INF_OR_UNBD: 'INF_OR_UNBD',
    gp.GRB.UNBOUNDED: 'UNBOUNDED',
    gp.GRB.TIME_LIMIT: 'TIME_LIMIT'
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [x[i].X for i in range(8)]
    projected_action = [int(values[i] >= 0.5) for i in range(8)]
    violations = [
        max(0.0, sum(values) - 3.0),
        max(0.0, sum(capacity[i] * values[i] for i in range(8)) - 6.0),
        max(0.0, 1.0 - (values[0] + values[3] + values[6])),
        max(0.0, 1.0 - (values[1] + values[4] + values[7])),
        max(0.0, 1.0 - (values[0] + values[3]))
    ]
    violations.extend(max(0.0, -v, v - 1.0) for v in values)
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in values)
    objective = model.ObjVal if math.isfinite(model.ObjVal) else None
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None
    objective = None

result = {
    'status': status,
    'objective': objective,
    'projected_action': projected_action,
    'max_constraint_violation': max_constraint_violation,
    'integrality_violation': integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))