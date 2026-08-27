from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: execute_candidate.py CODE.py")
    code_path = Path(sys.argv[1]).resolve()
    source = code_path.read_text(encoding="utf-8")

    import gurobipy as gp

    real_model = gp.Model
    models = []

    def tracking_model(*args, **kwargs):
        model = real_model(*args, **kwargs)
        models.append(model)
        return model

    gp.Model = tracking_model
    namespace = {"__name__": "__main__", "__file__": str(code_path)}
    exec(compile(source, str(code_path), "exec"), namespace, namespace)

    captures = []
    for model in models:
        status = int(getattr(model, "Status", 0) or 0)
        objective = None
        variables = []
        try:
            if int(getattr(model, "SolCount", 0) or 0) > 0:
                objective = float(model.ObjVal)
                variables = [
                    {
                        "name": str(variable.VarName),
                        "value": float(variable.X),
                        "type": str(variable.VType),
                    }
                    for variable in model.getVars()
                ]
        except Exception:
            objective = None
            variables = []
        captures.append(
            {
                "status": status,
                "objective": objective,
                "model_sense": int(getattr(model, "ModelSense", 0) or 0),
                "variables": variables,
            }
        )
    print("BASELINE_CAPTURE=" + json.dumps(captures, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
