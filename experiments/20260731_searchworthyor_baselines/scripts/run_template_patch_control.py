from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
from typing import Any

from audit_dataset import queryless_medoid_choice
from controlled_retrieval import FrozenBM25, read_jsonl


def load_solver_backend(dataset_root: Path):
    path = dataset_root / "scripts" / "solver_backend.py"
    spec = importlib.util.spec_from_file_location("searchworthyor_solver_backend", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def infer_patch(rule: str) -> str | None:
    if "不具备采用资格" in rule:
        return "eligibility_domain"
    if "不得在同一决策窗口共同启用" in rule:
        return "temporal_coupling"
    if "触发合规分支" in rule and "不可采用" in rule:
        return "conditional_auxiliary"
    if "最终组合必须至少包含" in rule:
        return "quota_risk_service_objective"
    return None


def substantive_rule(content: str) -> str:
    for line in content.splitlines():
        if "【实质规则】" in line:
            return line.split("】", 1)[1]
    return ""


def apply_template(base_ir: dict[str, Any], patch_class: str) -> dict[str, Any]:
    ir = copy.deepcopy(base_ir)
    ir["world"] = "patched"
    ir["model_id"] = f"{base_ir['task_id']}_template_control"
    action = list(ir["action_projection"])
    if patch_class == "eligibility_domain":
        variable = next(row for row in ir["variables"] if row["name"] == action[0])
        variable["ub"] = 0
        variable["domain_expression"] = f"{action[0]} = 0"
    elif patch_class == "temporal_coupling":
        ir["constraints"].append(
            {
                "name": "template_temporal_exclusion",
                "sense": "<=",
                "rhs": 1,
                "terms": {action[0]: 1, action[1]: 1},
                "expression": f"1*{action[0]} + 1*{action[1]} <= 1",
                "source": "template_control",
            }
        )
    elif patch_class == "conditional_auxiliary":
        ir["variables"].append(
            {
                "name": "z_trigger",
                "semantic_name": "外部规则触发状态",
                "vartype": "B",
                "lb": 0,
                "ub": 1,
                "domain_expression": "z_trigger in {0,1}",
            }
        )
        ir["constraints"].extend(
            [
                {
                    "name": "template_trigger_link",
                    "sense": "==",
                    "rhs": 0,
                    "terms": {action[0]: 1, "z_trigger": -1},
                    "expression": f"1*{action[0]} + -1*z_trigger == 0",
                    "source": "template_control",
                },
                {
                    "name": "template_trigger_exclusion",
                    "sense": "<=",
                    "rhs": 1,
                    "terms": {action[1]: 1, "z_trigger": 1},
                    "expression": f"1*{action[1]} + 1*z_trigger <= 1",
                    "source": "template_control",
                },
            ]
        )
    elif patch_class == "quota_risk_service_objective":
        ir["constraints"].append(
            {
                "name": "template_tail_service",
                "sense": ">=",
                "rhs": 1,
                "terms": {action[-2]: 1, action[-1]: 1},
                "expression": f"1*{action[-2]} + 1*{action[-1]} >= 1",
                "source": "template_control",
            }
        )
    else:
        raise ValueError(patch_class)
    return ir


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Patch-only negative control. It intentionally uses the Gold base IR and "
            "therefore is not an end-to-end baseline."
        )
    )
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    tasks = read_jsonl(args.dataset_root / "public" / "tasks_zh.jsonl")
    gold_rows = read_jsonl(args.dataset_root / "private" / "gold.jsonl")
    evidence_rows = read_jsonl(
        args.dataset_root / "private" / "evidence_corpus.jsonl"
    )
    gold_by_id = {row["id"]: row for row in gold_rows}
    evidence_by_id = {row["id"]: row for row in evidence_rows}
    index = FrozenBM25(evidence_rows)
    solver_backend = load_solver_backend(args.dataset_root)

    rows = []
    for task in tasks:
        gold = gold_by_id[task["id"]]
        if gold["evidence_mode"] != "fresh-private":
            continue
        query = " ".join([task["entity"], task["jurisdiction"], task["decision_time"]])
        candidates = index.search(query, 5)
        selected_id = queryless_medoid_choice(candidates)
        selected_document = evidence_by_id[selected_id]
        rule = substantive_rule(selected_document["content"])
        inferred = infer_patch(rule)
        base_ir = json.loads(
            (
                args.dataset_root / "models" / task["id"] / "base_ir.json"
            ).read_text(encoding="utf-8")
        )
        if inferred is None:
            predicted = None
            solve = {"status": "NO_PATCH"}
        else:
            predicted = apply_template(base_ir, inferred)
            solve = solver_backend.solve_gurobi(predicted)
        gold_solver = json.loads(
            (
                args.dataset_root / "models" / task["id"] / "solver_results.json"
            ).read_text(encoding="utf-8")
        )
        gold_actions = {
            tuple(action)
            for action in gold_solver["patched"]["exact_enumeration"][
                "optimal_actions"
            ]
        }
        predicted_action = tuple(solve.get("projected_action", []))
        objective_correct = (
            solve.get("status") == "OPTIMAL"
            and abs(
                float(solve["objective"])
                - float(
                    gold_solver["patched"]["exact_enumeration"]["objective"]
                )
            )
            <= 1e-6
        )
        rows.append(
            {
                "id": task["id"],
                "gold_patch_class": gold["patch_class"],
                "inferred_patch_class": inferred,
                "patch_class_correct": inferred == gold["patch_class"],
                "selected_evidence_id": selected_id,
                "gold_evidence_id": gold["applicability"]["selected_evidence_id"],
                "evidence_correct": selected_id
                == gold["applicability"]["selected_evidence_id"],
                "status": solve.get("status"),
                "action_correct": predicted_action in gold_actions,
                "objective_correct": objective_correct,
                "gold_base_ir_used": True,
            }
        )
    output = {
        "name": "metadata_bm25_top5_plus_medoid_plus_four_patch_templates",
        "scope": "fresh-private patch-only control",
        "not_end_to_end": True,
        "gold_base_ir_used": True,
        "n": len(rows),
        "evidence_accuracy": sum(row["evidence_correct"] for row in rows) / len(rows),
        "patch_class_accuracy": sum(row["patch_class_correct"] for row in rows)
        / len(rows),
        "action_accuracy": sum(row["action_correct"] for row in rows) / len(rows),
        "objective_accuracy": sum(row["objective_correct"] for row in rows)
        / len(rows),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {key: output[key] for key in [
                "n",
                "evidence_accuracy",
                "patch_class_accuracy",
                "action_accuracy",
                "objective_accuracy",
            ]},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
