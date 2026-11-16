"""Public-input-only worker for the ORLM C3 adapter experiment."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(ROOT), str(ROOT / "agent")]

from searchworthy.runtime import RunContext, write
from reevaluation.acquisition import AcquisitionTransport, ConfiguredTableLoopAgent
from reevaluation.standard import StandardAgent
from reevaluation.transport import ConfigurableResponsesTransport
from reevaluation.deepseek_search import DeepSeekSearchTransport
from free_variable_adapter import install
from copt_solver import solve as copt_solve


class CoptContext(RunContext):
    def solve(self, ir, label):
        self.reserve("solve", label=label)
        write(self.directory / "solver" / f"{self.resources['solve']:03}_{label}_ir.json", ir)
        result = copt_solve(ir, min(self.remaining(), self.config["budgets"]["solve_seconds"]))
        write(self.directory / "solver" / f"{self.resources['solve']:03}_{label}_result.json", result)
        self.event("SOLVE", label=label, status=result["status"], backend="COPT")
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--check-isolation", action="store_true")
    args = parser.parse_args()
    folder = args.directory.resolve()
    if not folder.is_relative_to(HERE / "batches"):
        raise ValueError("Expected a prepared folder inside this experiment's batches/")
    public_bytes = (folder / "input.json").read_bytes()
    public = json.loads(public_bytes)
    config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(public_bytes).hexdigest() == manifest["input_sha256"]
    assert hashlib.sha256((folder / "config.json").read_bytes()).hexdigest() == manifest["config_sha256"]
    assert set(public) == {"id", "prompt", "output_schema"}
    assert public["output_schema"]["actions"] == []
    for relative, sha in manifest["code_sha256"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == sha, relative
    adapter = install()
    output = folder / ("isolation" if args.check_isolation else "case")
    output.mkdir(exist_ok=False)
    access = (output / "access.jsonl").open("a", encoding="utf-8")

    def guard(event, arguments):
        if event not in {"open", "os.listdir", "os.scandir"} or not arguments or not isinstance(arguments[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(arguments[0])).resolve()
        if not path.is_relative_to(ROOT):
            return
        allowed = path.is_relative_to(output) or any(path.is_relative_to(p) for p in (ROOT / "agent", ROOT / "reevaluation"))
        access.write(json.dumps({"event": event, "path": str(path), "allowed": allowed}, ensure_ascii=False) + "\n")
        access.flush()
        if not allowed:
            raise PermissionError("Public-only worker denied access to another experiment/source file")

    sys.addaudithook(guard)
    probes = [HERE.parent / "SFT1991_sample20/SFT1991_sample20/B01_00413/答案.md",
              HERE.parent / "orlm_reference/reference_results.json", ROOT / "datasets/SearchWorthyOR-v1.6.3/private/gold.jsonl",
              HERE / "public_cases.jsonl", folder / "input.json"]
    for path in probes:
        try:
            path.read_bytes()
        except PermissionError:
            continue
        raise AssertionError("Data-isolation check failed")
    write(output / "isolation_verified.json", {"pass": True, "blocked_probes": len(probes),
                                               "public_input_loaded_before_guard": True, "adapter": adapter})
    if args.check_isolation:
        print("ISOLATION_PASS_NO_API_NO_SEARCH_NO_SOLVER")
        return 0
    ctx = CoptContext(output, config, config["method"], public["id"], live=True)
    agent = ConfiguredTableLoopAgent(ctx, public, None) if config["method"] == "swagent" else StandardAgent(ctx, public, None)
    transport = ConfigurableResponsesTransport(ctx, lambda: agent.revision)
    transport = DeepSeekSearchTransport(transport, ctx, lambda: agent.revision)
    agent.transport = AcquisitionTransport(transport, enabled=True)
    write(output / "version.json", {"manifest": manifest, "adapter": adapter, "solver": "COPT",
                                   "started_at_unix": time.time(), "reference_inputs_accessible": False})
    try:
        result = agent.run()
        summary = {"eval_id": public["id"], "method": config["method"], "stop_reason": result.get("stop_reason"),
                   "decision": result.get("decision"), "resources": ctx.resources}
    except Exception as exc:
        summary = {"eval_id": public["id"], "method": config["method"], "stop_reason": "WORKER_EXCEPTION",
                   "error_type": type(exc).__name__, "error": str(exc), "resources": ctx.resources}
        write(output / "worker_error.json", summary)
    write(output / "worker_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0 if summary["stop_reason"] != "WORKER_EXCEPTION" else 1


if __name__ == "__main__":
    raise SystemExit(main())

