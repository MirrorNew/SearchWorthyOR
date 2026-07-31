from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import sys
from pathlib import Path


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def gurobi_smoke() -> dict[str, object]:
    try:
        import gurobipy as gp
        from gurobipy import GRB

        model = gp.Model("searchworthyor_environment_smoke")
        model.Params.OutputFlag = 0
        variable = model.addVar(vtype=GRB.BINARY, name="x")
        model.setObjective(variable, GRB.MAXIMIZE)
        model.optimize()
        return {
            "available": True,
            "version": ".".join(map(str, gp.gurobi.version())),
            "status": "OPTIMAL" if model.Status == GRB.OPTIMAL else str(model.Status),
            "objective": float(model.ObjVal) if model.Status == GRB.OPTIMAL else None,
        }
    except Exception as exc:  # noqa: BLE001 - diagnostic output
        return {
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    workflow_root = Path(__file__).resolve().parents[2]
    baseline_root = Path(
        os.environ.get("SEARCHWORTHYOR_BASELINE_ROOT", "<LOCAL_BASELINES_ROOT>")
    )
    roots = {
        "optimus_prompt": baseline_root / "OptiMUS-main",
        "optimus_v02": baseline_root / "OptiMUS-optimus-v0.2",
        "chain_of_experts": baseline_root / "Chain-of-Experts-main",
        "optiminer_training_free": workflow_root,
    }
    codex_cli_raw = os.environ.get("CODEX_CLI") or shutil.which("codex") or ""
    codex_cli = Path(codex_cli_raw) if codex_cli_raw else Path("<CODEX_CLI>")
    output = {
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
        },
        "packages": {
            name: package_version(name)
            for name in ["gurobipy", "openai", "numpy", "langchain"]
        },
        "gurobi": gurobi_smoke(),
        "api_configuration": {
            "api_key_present": bool(
                os.environ.get("OPENOR_API_KEY") or os.environ.get("OPENAI_API_KEY")
            ),
            "base_url_present": bool(
                os.environ.get("OPENOR_BASE_URL")
                or os.environ.get("OPENAI_BASE_URL")
            ),
            "requested_model": "gpt-5.6-sol",
            "requested_reasoning_effort": "high",
            "strict_no_reasoning_fallback": True,
        },
        "codex_cli": {
            "path": str(codex_cli),
            "exists": codex_cli.is_file(),
            "sha256": file_sha256(codex_cli),
            "authentication": "existing ChatGPT/Codex CLI login",
            "reasoning_effort_requested": "high",
            "reasoning_effort_independently_validated": False,
        },
        "baseline_roots": {
            name: {"path": str(path), "exists": path.exists()}
            for name, path in roots.items()
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
