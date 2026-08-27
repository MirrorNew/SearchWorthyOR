from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from common import DATASET_ROOT, EXPERIMENT_ROOT, PUBLIC_INPUT_PATH, load_config, read_jsonl, write_json, write_jsonl


APP_GOLD_PATH = DATASET_ROOT / "private" / "applicability_gold.jsonl"
TASK_GOLD_PATH = DATASET_ROOT / "private" / "gold.jsonl"
SEARCH_NECESSITY_PATH = DATASET_ROOT / "private" / "search_necessity.jsonl"
PUBLIC_CASES_PATH = DATASET_ROOT / "public" / "applicability_cases_zh.jsonl"
MATRIX_PATH = EXPERIMENT_ROOT / "task_matrix.jsonl"
OPTIMINER_PACKET_PATH = EXPERIMENT_ROOT / "inputs" / "optiminer_benchmark.jsonl"
OPTIMINER_MAPPING_PATH = EXPERIMENT_ROOT / "inputs" / "optiminer_mapping.json"
PRIVATE_GOLD_PATH = EXPERIMENT_ROOT / "private" / "selected_gold.jsonl"


def objective_sense(path: Path) -> str:
    value = json.loads(path.read_text(encoding="utf-8"))
    objective = value.get("objective") if isinstance(value, dict) else None
    raw = str((objective or {}).get("sense") or (objective or {}).get("direction") or "").lower()
    if raw in {"max", "maximize", "maximise", "-1"}:
        return "max"
    if raw in {"min", "minimize", "minimise", "1"}:
        return "min"
    raise ValueError(f"unknown objective sense in {path}")


def expected_case_ids() -> list[str]:
    return [f"SWOR-R{index:03d}-C{case}" for index in range(1, 121) for case in (1, 2)]


def build() -> dict[Path, Any]:
    config = load_config()
    source_rows = read_jsonl(PUBLIC_CASES_PATH)
    app_gold = {str(row["case_id"]): row for row in read_jsonl(APP_GOLD_PATH)}
    task_gold = {str(row["id"]): row for row in read_jsonl(TASK_GOLD_PATH)}
    search_need = {str(row["task_id"]): row for row in read_jsonl(SEARCH_NECESSITY_PATH)}
    expected = expected_case_ids()
    if [row.get("case_id") for row in source_rows] != expected:
        raise ValueError("V1.5.1 public cases must be ordered as SWOR-R001-C1/C2 through SWOR-R120-C1/C2")
    if len(app_gold) != 240 or len(task_gold) != 120 or len(search_need) != 120:
        raise ValueError("V1.5.1 private scorer inputs have unexpected cardinality")

    public_rows: list[dict[str, Any]] = []
    selected_gold: list[dict[str, Any]] = []
    benchmark: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, str]] = []
    for index, source in enumerate(source_rows, start=1):
        case_id = str(source["case_id"])
        source_task_id = str(source["source_task_id"])
        gold = app_gold.get(case_id)
        task = task_gold.get(source_task_id)
        necessity = search_need.get(source_task_id)
        if gold is None or task is None or necessity is None:
            raise ValueError(f"{case_id}: scorer identity is incomplete")
        if gold.get("source_task_id") != source_task_id:
            raise ValueError(f"{case_id}: public/private source-task mismatch")
        expected_state = "RETAIN" if case_id.endswith("-C1") else "PATCH_CHANGES"
        if gold.get("decision_state") != expected_state:
            raise ValueError(f"{case_id}: unexpected decision state")
        if expected_state == "RETAIN" and (gold.get("applicability") is not False or gold.get("gold_patch_elements") != []):
            raise ValueError(f"{case_id}: RETAIN must have applicability=false and an empty Patch")
        if expected_state == "PATCH_CHANGES" and (gold.get("applicability") is not True or not gold.get("gold_patch_elements")):
            raise ValueError(f"{case_id}: PATCH_CHANGES must have applicability=true and a non-empty Patch")

        public_rows.append({"id": source_task_id, "case_id": case_id, "prompt_zh": source["prompt_zh"]})
        model_key = "base_model_path" if expected_state == "RETAIN" else "patched_model_path"
        selected_gold.append(
            {
                "task_id": case_id,
                "source_task_id": source_task_id,
                "case_id": case_id,
                "pair_id": gold["pair_id"],
                "task_mode": task["task_mode"],
                "decision_state": expected_state,
                "applicability": gold["applicability"],
                "gold_patch_elements": gold["gold_patch_elements"],
                "gold_action_set": gold["gold_action_set"],
                "gold_objective": gold["gold_objective"],
                "objective_sense": objective_sense(DATASET_ROOT / task[model_key]),
                "changed_factor": gold.get("changed_factor"),
                "official_support": gold.get("official_support", []),
                "specific_official_rule_required": necessity.get("specific_official_rule_required"),
            }
        )
        runner_id = f"OMB{index:03d}"
        benchmark.append(
            {
                "id": runner_id,
                "source": "SearchWorthyOR-v1.5.1 canonical prompt_zh only",
                "type": "",
                "scenario": "native_arxiv_retrieval",
                "problem": source["prompt_zh"],
                "answer": "PRIVATE_GOLD_NOT_AVAILABLE_TO_RUNNER",
            }
        )
        mapping_rows.append(
            {"runner_id": runner_id, "task_id": case_id, "source_task_id": source_task_id, "case_id": case_id}
        )

    methods = list(config["methods"])
    matrix = [
        {
            "case_id": row["case_id"],
            "source_task_id": row["id"],
            "instance_id": f"{method}|{row['case_id']}",
            "method": method,
            "status": "PLANNED",
            "task_id": row["case_id"],
        }
        for method in methods
        for row in public_rows
    ]
    if len(matrix) != 1200 or len({row["instance_id"] for row in matrix}) != 1200:
        raise ValueError("five-baseline matrix is not 1,200 unique instances")
    strata = Counter(row["task_mode"] for row in selected_gold)
    if strata != {"single_hop_control": 120, "multi_hop_revision": 120}:
        raise ValueError(f"paired task-mode strata changed: {strata}")
    states = Counter(row["decision_state"] for row in selected_gold)
    if states != {"RETAIN": 120, "PATCH_CHANGES": 120}:
        raise ValueError(f"paired decision-state strata changed: {states}")
    return {
        PUBLIC_INPUT_PATH: public_rows,
        MATRIX_PATH: matrix,
        PRIVATE_GOLD_PATH: selected_gold,
        OPTIMINER_PACKET_PATH: benchmark,
        OPTIMINER_MAPPING_PATH: {"rows": mapping_rows},
    }


def same_jsonl(path: Path, rows: list[dict[str, Any]]) -> bool:
    return path.is_file() and read_jsonl(path) == rows


def same_json(path: Path, value: Any) -> bool:
    return path.is_file() and json.loads(path.read_text(encoding="utf-8")) == value


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare isolated SearchWorthyOR V1.5.1 five-baseline inputs")
    parser.add_argument("--check", action="store_true", help="verify prepared files without modifying them")
    args = parser.parse_args()
    outputs = build()
    if args.check:
        mismatches = [
            str(path)
            for path, value in outputs.items()
            if not (same_jsonl(path, value) if isinstance(value, list) else same_json(path, value))
        ]
        if mismatches:
            raise SystemExit("prepared file mismatch: " + ", ".join(mismatches))
        print(json.dumps({"status": "PASS", "public_cases": 240, "matrix": 1200, "optiminer_rows": 240}, ensure_ascii=False))
        return
    if any(path.exists() for path in outputs):
        raise SystemExit("refusing to overwrite prepared V1.5.1 inputs; use --check")
    for path, value in outputs.items():
        if isinstance(value, list):
            write_jsonl(path, value)
        else:
            write_json(path, value)
    print(json.dumps({"status": "PREPARED", "public_cases": 240, "matrix": 1200, "optiminer_rows": 240}, ensure_ascii=False))


if __name__ == "__main__":
    main()
