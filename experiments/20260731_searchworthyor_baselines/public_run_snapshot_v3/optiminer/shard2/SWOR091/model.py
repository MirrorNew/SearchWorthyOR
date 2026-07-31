import gurobipy as gp
import json
import math

ir = json.loads(r'''{"model_id":"SWOR091_patched","world":{"decision_date":"2026-03-05","entity":"星桥综合服务运营有限公司（东岚经营辖区（合成）岚桥单元）","jurisdiction":"东岚经营辖区（合成）","activity":"排班与劳动力资源重排"},"sense":"max","single_objective":true,"variables":[{"name":"x_0","vartype":"B","lb":0,"ub":1,"semantic_name":"班次A（基础类别；关键工时点1）"},{"name":"x_1","vartype":"B","lb":0,"ub":1,"semantic_name":"班次B（基础类别；关键工时点2）"},{"name":"x_2","vartype":"B","lb":0,"ub":1,"semantic_name":"班次C（基础类别；关键工时点3）"},{"name":"x_3","vartype":"B","lb":0,"ub":1,"semantic_name":"班次D（基础类别；关键工时点4）"},{"name":"x_4","vartype":"B","lb":0,"ub":1,"semantic_name":"班次E（保障类别1；关键工时点1）"},{"name":"x_5","vartype":"B","lb":0,"ub":1,"semantic_name":"班次F（保障类别2；关键工时点2）"}],"objective":{"constant":0,"terms":{"x_0":1014,"x_1":953,"x_2":911,"x_3":850,"x_4":789,"x_5":747}},"constraints":[{"name":"select_exactly_3","sense":"==","rhs":3,"terms":{"x_0":1,"x_1":1,"x_2":1,"x_3":1,"x_4":1,"x_5":1}},{"name":"cover_period_1","sense":">=","rhs":1,"terms":{"x_0":1,"x_3":1}},{"name":"cover_period_2","sense":">=","rhs":1,"terms":{"x_1":1,"x_4":1}},{"name":"cover_period_3","sense":">=","rhs":1,"terms":{"x_2":1,"x_5":1}},{"name":"core_candidates_min_2","sense":">=","rhs":2,"terms":{"x_0":1,"x_1":1,"x_2":1}},{"name":"policy_ab_mutual_exclusion","sense":"<=","rhs":1,"terms":{"x_0":1,"x_1":1}}],"action_projection":["x_0","x_1","x_2","x_3","x_4","x_5"]}''')

model = gp.Model(ir["model_id"])
model.Params.OutputFlag = 0
model.Params.Threads = 1
model.Params.PoolSearchMode = 2
model.Params.PoolSolutions = 100

x = {}
for spec in ir["variables"]:
    x[spec["name"]] = model.addVar(
        lb=spec["lb"],
        ub=spec["ub"],
        vtype=gp.GRB.BINARY,
        name=spec["name"]
    )

objective = gp.LinExpr(ir["objective"]["constant"])
for name, coefficient in ir["objective"]["terms"].items():
    objective += coefficient * x[name]
model.setObjective(objective, gp.GRB.MAXIMIZE)

for spec in ir["constraints"]:
    lhs = gp.quicksum(coefficient * x[name] for name, coefficient in spec["terms"].items())
    if spec["sense"] == "<=":
        model.addConstr(lhs <= spec["rhs"], name=spec["name"])
    elif spec["sense"] == ">=":
        model.addConstr(lhs >= spec["rhs"], name=spec["name"])
    elif spec["sense"] == "==":
        model.addConstr(lhs == spec["rhs"], name=spec["name"])
    else:
        raise ValueError("Unsupported constraint sense: " + spec["sense"])

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    optimal_actions = []
    best_objective = model.ObjVal
    for solution_number in range(model.SolCount):
        model.Params.SolutionNumber = solution_number
        if math.isclose(model.PoolObjVal, best_objective, rel_tol=1e-9, abs_tol=1e-6):
            action = [int(round(x[name].Xn)) for name in ir["action_projection"]]
            if action not in optimal_actions:
                optimal_actions.append(action)
    optimal_actions.sort()
    projected_action = optimal_actions[0]
    values = {name: projected_action[index] for index, name in enumerate(ir["action_projection"])}

    max_constraint_violation = 0.0
    for spec in ir["constraints"]:
        lhs_value = sum(coefficient * values[name] for name, coefficient in spec["terms"].items())
        if spec["sense"] == "<=":
            violation = max(0.0, lhs_value - spec["rhs"])
        elif spec["sense"] == ">=":
            violation = max(0.0, spec["rhs"] - lhs_value)
        else:
            violation = abs(lhs_value - spec["rhs"])
        max_constraint_violation = max(max_constraint_violation, violation)

    for spec in ir["variables"]:
        value = values[spec["name"]]
        max_constraint_violation = max(
            max_constraint_violation,
            max(0.0, spec["lb"] - value),
            max(0.0, value - spec["ub"])
        )
    integrality_violation = max(abs(value - round(value)) for value in values.values())
    result = {
        "status": status,
        "objective": best_objective,
        "projected_action": projected_action,
        "all_optimal_projected_actions": optimal_actions,
        "max_constraint_violation": max_constraint_violation,
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": None,
        "all_optimal_projected_actions": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))
