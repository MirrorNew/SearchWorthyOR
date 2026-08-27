from __future__ import annotations

import ast
import inspect
import json
from collections import Counter
from pathlib import Path
from typing import Any

import common
import gated_search_pipeline
import run_all_parallel
import run_direct
import run_local
import run_optiminer
import run_search_first
import web_retrieval


ROOT = common.EXPERIMENT_ROOT
MATRIX_PATH = ROOT / "task_matrix.jsonl"
GOLD_PATH = ROOT / "private" / "selected_gold.jsonl"
OPTIMINER_PACKET_PATH = ROOT / "inputs" / "optiminer_benchmark.jsonl"
OPTIMINER_MAPPING_PATH = ROOT / "inputs" / "optiminer_mapping.json"
REPORT_PATH = ROOT / "runs" / "offline" / "gate_summary.json"
RUNNER_FILES = (
    "common.py",
    "candidate_adapter.py",
    "execute_candidate.py",
    "web_retrieval.py",
    "gated_search_pipeline.py",
    "run_direct.py",
    "run_search_first.py",
    "run_local.py",
    "run_optiminer.py",
    "run_all_parallel.py",
)
METHODS = (
    "Direct-v2 Base-Solve Gated Search",
    "CoE",
    "OptiMUS",
    "optiminer-training-free",
    "Search-First Gated Raw-NL",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".", 1)[0])
    return names


def safe_env_contract() -> dict[str, Any]:
    names: list[str] = []
    nonempty: dict[str, bool] = {}
    for raw_line in common.DEFAULT_ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        require("=" in line, ".env.local contains a malformed line")
        key, value = line.split("=", 1)
        key = key.strip()
        names.append(key)
        nonempty[key] = bool(value.strip())
    require(names == ["OPENOR_BASE_URL", "OPENOR_API_KEY"], ".env.local must contain only the two fixed keys")
    require(all(nonempty.values()), ".env.local contains an empty required value")
    require(common.DEFAULT_ENV_FILE.resolve() == (ROOT / ".env.local").resolve(), "credential source is not experiment-local")
    config = common.load_config()
    require(config["provider"]["name"] == "shubiaobiao", "provider is not Shubiaobiao")
    require(config["provider"]["provider_fallback"] is False, "provider fallback must remain disabled")
    return {"names": names, "all_nonempty": True, "provider": "shubiaobiao", "fallback": False}


def public_and_matrix_contract() -> dict[str, Any]:
    public = common.public_cases()
    expected_ids = {f"SWOR-R{index:03d}-C{case}" for index in range(1, 121) for case in (1, 2)}
    require(len(public) == 240 and set(public) == expected_ids, "public input must contain all 240 paired case IDs")
    require(all(row["case_id"] == case_id for case_id, row in public.items()), "public case identity mismatch")
    require(all(row["id"] == row["case_id"].rsplit("-C", 1)[0] for row in public.values()), "source-task identity mismatch")
    require(all(set(row) == {"id", "case_id", "prompt_zh"} for row in public.values()), "runner public fields changed")
    for row in public.values():
        common.output_schema_for(row)

    matrix = common.read_jsonl(MATRIX_PATH)
    require(len(matrix) == 1200, "matrix must contain 1,200 instances")
    require(len({row.get("instance_id") for row in matrix}) == 1200, "matrix instance identity is not unique")
    require(Counter(row.get("method") for row in matrix) == Counter({method: 240 for method in METHODS}), "matrix method counts changed")
    require(all(row.get("status") == "PLANNED" and row.get("task_id") == row.get("case_id") for row in matrix), "matrix status or case identity changed")
    return {"public_rows": len(public), "matrix_rows": len(matrix), "unique_method_case": 1200}


def scorer_only_contract() -> dict[str, Any]:
    require(GOLD_PATH.is_file(), "scorer-only selected_gold.jsonl has not been prepared")
    require(OPTIMINER_PACKET_PATH.is_file() and OPTIMINER_MAPPING_PATH.is_file(), "optiminer packet/mapping has not been prepared")
    gold = common.read_jsonl(GOLD_PATH)
    packet = common.read_jsonl(OPTIMINER_PACKET_PATH)
    mapping = common.read_json(OPTIMINER_MAPPING_PATH)
    require(len(gold) == len(packet) == 240, "scorer-only Gold or optiminer packet row count changed")
    states = Counter(row.get("decision_state") for row in gold)
    require(states == {"RETAIN": 120, "PATCH_CHANGES": 120}, "paired decision-state balance changed")
    require(all((row["applicability"] is False and row["gold_patch_elements"] == []) if row["decision_state"] == "RETAIN" else (row["applicability"] is True and bool(row["gold_patch_elements"])) for row in gold), "decision/applicability/Patch contract changed")
    require(all(set(row) == {"id", "source", "type", "scenario", "problem", "answer"} and row["answer"] == "PRIVATE_GOLD_NOT_AVAILABLE_TO_RUNNER" for row in packet), "optiminer runner packet exposes extra fields")
    rows = mapping.get("rows") if isinstance(mapping, dict) else None
    require(isinstance(rows, list) and len(rows) == 240, "optiminer mapping changed")
    require(len({row.get("task_id") for row in rows}) == 240 and all(row.get("task_id") == row.get("case_id") for row in rows), "optiminer case mapping is not one-to-one")
    return {"gold_rows": len(gold), "retain": states["RETAIN"], "patch_changes": states["PATCH_CHANGES"], "optiminer_rows": len(packet)}


def import_and_method_boundary_contract() -> dict[str, Any]:
    forbidden_imports = {"prepare_harness", "score_report", "offline_gate"}
    for name in RUNNER_FILES:
        path = ROOT / "scripts" / name
        imports = imported_modules(path)
        require(not imports.intersection(forbidden_imports), f"{name} imports a scorer/private preparation module")
        source = path.read_text(encoding="utf-8").lower()
        require("selected_gold" not in source and "applicability_gold.jsonl" not in source and "private\\gold.jsonl" not in source, f"{name} references Private Gold")
        require("sha256" not in source and "freeze_manifest" not in source, f"{name} contains a prohibited hash/freeze workflow")
    local_source = inspect.getsource(run_local)
    require("web_search(" not in local_source and "PublicWebRetriever" not in local_source, "CoE/OptiMUS gained web retrieval")
    command = run_optiminer.runner_command(ROOT, OPTIMINER_PACKET_PATH, "OMB001", ROOT, "http://127.0.0.1:1/v1")
    require(command[command.index("--search-backend") + 1] == "arxiv_document", "optiminer is not Arxiv-only")
    require(run_optiminer.PHYSICAL_SHORT_ROOT.resolve().is_relative_to(ROOT.resolve()), "optiminer native workspace is outside the experiment root")
    return {"runner_files": len(RUNNER_FILES), "private_imports": 0, "coe_optimus_web": 0, "optiminer_backend": "arxiv_document", "optiminer_workspace_in_experiment": True}


def chain12_contract() -> dict[str, Any]:
    config = common.load_config()
    profile = common.shared_search_config(config)
    require(config["methods"][run_direct.METHOD]["search_profile"] == config["methods"][run_search_first.METHOD]["search_profile"] == "shubiaobiao_hosted_search_shared", "Chain1/2 do not share one Shubiaobiao profile")
    require(run_direct.run_one.__globals__["run_case"] is run_search_first.run_one.__globals__["run_case"], "Chain1/2 do not share the retrieval executor")
    require("Build and solve the Base" in gated_search_pipeline.BASE_SYSTEM, "Chain1 lacks formal Base modeling")
    require("base_solver_attempt" in gated_search_pipeline.DIRECT_GATE_SYSTEM or "Base OR model" in gated_search_pipeline.DIRECT_GATE_SYSTEM, "Chain1 gate is not model-aware")
    require("only the supplied public prompt_zh" in gated_search_pipeline.SEARCH_FIRST_GATE_SYSTEM, "Chain2 gate is not prompt-only")
    require("Do not formulate" in gated_search_pipeline.SEARCH_FIRST_GATE_SYSTEM, "Chain2 gate allows pre-modeling")
    require("retrieved_evidence_raw_nl" in gated_search_pipeline.SEARCH_FIRST_FINAL_SYSTEM, "Chain2 final request does not bind Raw-NL")
    require(profile["max_queries_per_case"] == 3, "search-query budget is not three")
    require(profile["max_opened_pages_per_query"] == 3 and profile["max_page_attempts_per_query"] == 6, "page success/attempt budget changed")
    open_source = inspect.getsource(web_retrieval.PublicWebRetriever.open_top)
    require("for result in results:" in open_source and "len(pages) >= self.max_open" in open_source, "failed pages still consume the success budget")
    require(set(run_all_parallel.METHODS) == {"direct", "coe", "optimus", "optiminer", "search_first"}, "orchestration does not contain five methods")
    require(config["phases"]["smoke"]["instances"] == 10 and config["phases"]["formal"]["instances"] == 1200, "Smoke/Formal instance counts changed")
    require(config["parallelism"]["smoke_total_workers"] == 5 and all(value["smoke_workers"] == 1 for value in config["methods"].values()), "five-method Smoke concurrency changed")
    require(config["parallelism"]["formal_total_workers"] == 15 and all(value["formal_workers"] == 3 for value in config["methods"].values()), "Formal concurrency changed")
    return {"shared_profile": profile, "allowed_differences": config["chain12_parity_contract"]["only_allowed_differences"], "smoke_instances": 10, "formal_instances": 1200}


def main() -> None:
    summary = {
        "schema_version": "searchworthyor.v151.five_baselines.offline_gate.v1",
        "status": "PASS",
        "environment": safe_env_contract(),
        "public_matrix": public_and_matrix_contract(),
        "scorer_only": scorer_only_contract(),
        "method_boundaries": import_and_method_boundary_contract(),
        "chain12": chain12_contract(),
    }
    common.write_json(REPORT_PATH, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
