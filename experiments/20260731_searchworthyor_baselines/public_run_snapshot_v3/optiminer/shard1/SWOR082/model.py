import gurobipy as gp
import json
import math

m = gp.Model("SWOR082_patched")
m.Params.OutputFlag = 0
m.Params.Threads = 1
m.Params.Seed = 0
m.Params.MIPGap = 0.0
m.Params.PoolSearchMode = 2
m.Params.PoolSolutions = 16
m.Params.PoolGap = 0.0

# MODEL_VARIABLES
x = [m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

# MODEL_OBJECTIVE
benefit = [1007, 965, 904, 843, 801, 740]
m.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

# BASE_SEGMENT_1
m.addConstr(x[0] + x[3] == 1, name="segment_1_exactly_one")
# BASE_SEGMENT_2
m.addConstr(x[1] + x[4] == 1, name="segment_2_exactly_one")
# BASE_SEGMENT_3
m.addConstr(x[2] + x[5] == 1, name="segment_3_exactly_one")
# BASE_BACKUP_EXCLUSION
m.addConstr(x[4] + x[5] <= 1, name="backup_mutual_exclusion")
# POLICY_DOC_EF738A44A6A5653F
m.addConstr(x[0] + x[1] <= 1, name="policy_A_B_mutual_exclusion")

m.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
    gp.GRB.SUBOPTIMAL: "SUBOPTIMAL"
}
status = status_names.get(m.Status, str(m.Status))

if m.SolCount > 0:
    # SOLUTION_SELECTION: choose the lexicographically largest action only as
    # deterministic post-processing among solutions attaining the same primary optimum.
    optimum = float(m.ObjVal)
    candidates = []
    for solution_number in range(m.SolCount):
        m.Params.SolutionNumber = solution_number
        pool_objective = float(m.PoolObjVal)
        raw = [float(v.Xn) for v in x]
        bits = [int(round(value)) for value in raw]
        if math.isclose(pool_objective, optimum, rel_tol=0.0, abs_tol=1e-6):
            candidates.append((bits, raw))
    if not candidates:
        raw = [float(v.X) for v in x]
        candidates = [([int(round(value)) for value in raw], raw)]
    projected_action, raw_values = max(candidates, key=lambda item: item[0])
    objective = float(sum(benefit[i] * projected_action[i] for i in range(6)))

    checks = [
        ("==", raw_values[0] + raw_values[3], 1.0),
        ("==", raw_values[1] + raw_values[4], 1.0),
        ("==", raw_values[2] + raw_values[5], 1.0),
        ("<=", raw_values[4] + raw_values[5], 1.0),
        ("<=", raw_values[0] + raw_values[1], 1.0)
    ]
    violations = []
    for sense, lhs, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    max_constraint_violation = float(max(violations, default=0.0))
    integrality_violation = float(max((abs(value - round(value)) for value in raw_values), default=0.0))
    tie_count = len(candidates)
else:
    objective = None
    projected_action = [0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None
    tie_count = 0

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
    "optimal_action_tie_count": tie_count,
    "selection_rule": "lexicographically_largest_among_primary_optima"
}, ensure_ascii=False))