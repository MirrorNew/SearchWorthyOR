"""Instrument solver outputs without rewriting the supplied modeling program."""
import json
from pathlib import Path
import runpy
import sys

import coptpy as cp

program, output = Path(sys.argv[1]), Path(sys.argv[2])
OriginalEnvr = cp.Envr
model_count = 0


class ModelProxy:
    def __init__(self, actual):
        global model_count
        self.actual = actual
        self.number = model_count
        model_count += 1

    def __getattr__(self, name):
        return getattr(self.actual, name)

    def solve(self, *args, **kwargs):
        self.actual.setParam(cp.COPT.Param.TimeLimit, 90)
        self.actual.setParam(cp.COPT.Param.Threads, 1)
        self.actual.write(str(output / f"reference_model_{self.number}.mps"))
        result = self.actual.solve(*args, **kwargs)
        stats = {"status": self.actual.status, "time_limit_seconds": 90, "threads": 1}
        for attr in ("ObjVal", "BestBnd", "MipGap", "SolvingTime", "NumVars", "NumConstrs"):
            try:
                stats[attr] = self.actual.getAttr(attr)
            except Exception:
                pass
        (output / f"solver_stats_{self.number}.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
        return result


class EnvrProxy:
    def __init__(self, *args, **kwargs):
        self.actual = OriginalEnvr(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.actual, name)

    def createModel(self, *args, **kwargs):
        return ModelProxy(self.actual.createModel(*args, **kwargs))


cp.Envr = EnvrProxy
runpy.run_path(str(program), run_name="__main__")
