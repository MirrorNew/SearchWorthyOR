"""Independent-solver check of exported reference mathematics, not task semantics."""
import json
from pathlib import Path

import gurobipy as gp

OUT = Path(__file__).resolve().parent
records = json.loads((OUT / "reference_results.json").read_text(encoding="utf-8"))
checks = []
with gp.Env(empty=True) as env:
    env.setParam("OutputFlag", 0)
    env.start()
    for row in records:
        path = OUT / "cases" / row["source_id"] / "reference_model_0.mps"
        with gp.read(str(path), env=env) as model:
            model.Params.TimeLimit = 90
            model.Params.Threads = 1
            model.Params.MIPGap = 1e-9
            expected = row["result"]["objective_value"]
            try:
                model.optimize()
            except gp.GurobiError as exc:
                check = {"source_id": row["source_id"], "reference_objective": expected,
                         "status": "SOLVER_UNAVAILABLE", "error": str(exc), "error_code": exc.errno,
                         "variables": model.NumVars, "constraints": model.NumConstrs,
                         "source_unchanged": row["source_unchanged"], "pass": None}
                checks.append(check)
                print(json.dumps(check), flush=True)
                continue
            check = {"source_id": row["source_id"], "gurobi_status": model.Status,
                     "reference_objective": expected, "gurobi_objective": model.ObjVal if model.SolCount else None,
                     "gurobi_bound": model.ObjBound, "variables": model.NumVars, "constraints": model.NumConstrs,
                     "source_unchanged": row["source_unchanged"]}
            check["pass"] = model.Status == gp.GRB.OPTIMAL and abs(model.ObjVal - expected) <= max(1e-6, abs(expected) * 1e-8)
            checks.append(check)
            print(json.dumps(check), flush=True)
(OUT / "reference_crosscheck.json").write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
assert len(checks) == 20 and all(c["pass"] is not False for c in checks)
