import gurobipy as gp
import json
import math


def main():
    model = gp.Model("SWOR047")
    model.Params.OutputFlag = 0

    x = [
        model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}")
        for i in range(8)
    ]

    benefits = [1011, 950, 908, 847, 805, 744, 683, 641]
    capacities = [2, 3, 4, 1, 2, 3, 4, 1]

    model.setObjective(
        gp.quicksum(benefits[i] * x[i] for i in range(8)),
        gp.GRB.MAXIMIZE,
    )
    model.addConstr(gp.quicksum(x) <= 3, name="max_enabled_3")
    model.addConstr(
        gp.quicksum(capacities[i] * x[i] for i in range(8)) <= 9,
        name="capacity_limit_9",
    )
    model.addConstr(x[0] + x[3] >= 1, name="core_A_or_backup_D")
    model.addConstr(x[0] + x[1] <= 1, name="regulatory_A_B_mutex")

    model.optimize()

    status_names = {
        gp.GRB.OPTIMAL: "OPTIMAL",
        gp.GRB.INFEASIBLE: "INFEASIBLE",
        gp.GRB.UNBOUNDED: "UNBOUNDED",
        gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
        gp.GRB.TIME_LIMIT: "TIME_LIMIT",
        gp.GRB.SUBOPTIMAL: "SUBOPTIMAL",
    }
    status = status_names.get(model.Status, str(model.Status))

    if model.SolCount > 0:
        raw = [x[i].X for i in range(8)]
        projected = [int(round(value)) for value in raw]
        enabled_lhs = sum(raw)
        capacity_lhs = sum(capacities[i] * raw[i] for i in range(8))
        core_lhs = raw[0] + raw[3]
        mutex_lhs = raw[0] + raw[1]
        max_violation = max(
            0.0,
            enabled_lhs - 3.0,
            capacity_lhs - 9.0,
            1.0 - core_lhs,
            mutex_lhs - 1.0,
        )
        integrality_violation = max(
            abs(value - round(value)) for value in raw
        )
        objective = float(model.ObjVal)
    else:
        projected = [0] * 8
        max_violation = None
        integrality_violation = None
        objective = None

    result = {
        "status": status,
        "objective": objective,
        "projected_action": projected,
        "max_constraint_violation": max_violation,
        "integrality_violation": integrality_violation,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
