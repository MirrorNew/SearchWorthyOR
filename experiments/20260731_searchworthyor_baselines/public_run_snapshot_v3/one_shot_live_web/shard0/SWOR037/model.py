import gurobipy as gp
import json
import math

m = gp.Model("SWOR037_patched")
m.Params.OutputFlag = 0

x = [m.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

values = [1013, 952, 910, 849, 788, 746, 685, 643]
m.setObjective(gp.quicksum(values[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

m.addConstr(gp.quicksum(x) <= 3, name="max_three_modules")
m.addConstr(x[0] + x[3] + x[6] >= 1, name="zone_1_connectivity")
m.addConstr(x[1] + x[4] + x[7] >= 1, name="zone_2_connectivity")
m.addConstr(x[2] + x[5] >= 1, name="zone_3_connectivity")
m.addConstr(-x[0] + x[1] + x[4] >= 0, name="a_requires_b_or_e")
m.addConstr(x[0] + x[3] >= 1, name="a_or_d_required")
m.addConstr(-x[0] + x[6] + x[7] >= 0, name="ca_rest_coverage_if_a")
m.addConstr(x[0] + x[1] <= 1, name="ca_no_work_in_only_rest_window")

m.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(m.Status, str(m.Status))

if m.SolCount > 0:
    solution = [v.X for v in x]
    projected_action = [int(round(v)) for v in solution]
    objective = float(m.ObjVal)
    max_constraint_violation = 0.0
    for constr in m.getConstrs():
        row = m.getRow(constr)
        activity = sum(row.getCoeff(i) * row.getVar(i).X for i in range(row.size()))
        if constr.Sense == "<":
            violation = max(0.0, activity - constr.RHS)
        elif constr.Sense == ">":
            violation = max(0.0, constr.RHS - activity)
        else:
            violation = math.fabs(activity - constr.RHS)
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(math.fabs(v - round(v)) for v in solution)
else:
    objective = None
    projected_action = [0 for _ in x]
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))