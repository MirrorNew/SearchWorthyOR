import gurobipy
import json
import math

m = gurobipy.Model("SWOR092_patched")
m.Params.OutputFlag = 0

x = [m.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

# OBJECTIVE_TOTAL_COVERAGE
m.setObjective(
    1000 * x[0] + 958 * x[1] + 897 * x[2] + 855 * x[3]
    + 794 * x[4] + 752 * x[5] + 691 * x[6],
    gurobipy.GRB.MAXIMIZE,
)

# BASE_SELECT_EXACTLY_3
m.addConstr(sum(x) == 3, name="select_exactly_3")
# BASE_COVER_PERIOD_1
m.addConstr(x[0] + x[3] + x[6] >= 1, name="cover_period_1")
# BASE_COVER_PERIOD_2_FROZEN
m.addConstr(x[1] + x[4] >= 1, name="cover_period_2_frozen")
# BASE_COVER_PERIOD_3
m.addConstr(x[2] + x[5] >= 1, name="cover_period_3")
# BASE_EXACTLY_ONE_B_E_G
m.addConstr(x[1] + x[4] + x[6] == 1, name="exactly_one_B_E_G")
# PATCH_WAC_296_126_092_REST_BREAK
m.addConstr(x[5] + x[6] >= 1, name="wa_paid_rest_break_for_four_hours")

m.optimize()

status_names = {
    1: "LOADED",
    2: "OPTIMAL",
    3: "INFEASIBLE",
    4: "INF_OR_UNBD",
    5: "UNBOUNDED",
    6: "CUTOFF",
    7: "ITERATION_LIMIT",
    8: "NODE_LIMIT",
    9: "TIME_LIMIT",
    10: "SOLUTION_LIMIT",
    11: "INTERRUPTED",
    12: "NUMERIC",
    13: "SUBOPTIMAL",
    14: "INPROGRESS",
    15: "USER_OBJ_LIMIT",
}

if m.SolCount > 0:
    values = [float(v.X) for v in x]
    projected = [int(round(v)) for v in values]
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, 1.0 - (values[0] + values[3] + values[6])),
        max(0.0, 1.0 - (values[1] + values[4])),
        max(0.0, 1.0 - (values[2] + values[5])),
        abs(values[1] + values[4] + values[6] - 1.0),
        max(0.0, 1.0 - (values[5] + values[6])),
    ]
    objective = float(m.ObjVal)
    if not math.isfinite(objective):
        objective = None
    result = {
        "status": status_names.get(m.Status, str(m.Status)),
        "objective": objective,
        "projected_action": projected,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(v - round(v)) for v in values),
    }
else:
    result = {
        "status": status_names.get(m.Status, str(m.Status)),
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None,
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))