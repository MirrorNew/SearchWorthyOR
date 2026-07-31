from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a Gold-derived fixture used only to test the scorer."
    )
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    gold_rows = read_jsonl(args.dataset_root / "private" / "gold.jsonl")
    rows = []
    for gold in gold_rows:
        task_id = gold["id"]
        model_dir = args.dataset_root / "models" / task_id
        base_ir = json.loads((model_dir / "base_ir.json").read_text(encoding="utf-8"))
        patched_ir = json.loads(
            (model_dir / "patched_ir.json").read_text(encoding="utf-8")
        )
        solver = json.loads(
            (model_dir / "solver_results.json").read_text(encoding="utf-8")
        )
        evidence_id = gold["applicability"]["selected_evidence_id"]
        rows.append(
            {
                "task_id": task_id,
                "baseline": "oracle_scorer_fixture_not_a_baseline",
                "condition": "oracle_evidence",
                "requested_model": "fixture",
                "actual_model": "fixture",
                "requested_reasoning_effort": "high",
                "reasoning_fallback": False,
                "generated_once": True,
                "search_trace": [
                    {
                        "query": "<oracle-fixture>",
                        "results": [{"rank": 1, "id": evidence_id, "score": 1.0}],
                    }
                ],
                "selected_evidence_ids": [evidence_id],
                "applicability": gold["applicability"],
                "base_ir": base_ir,
                "typed_patch": gold["typed_patch"],
                "patched_ir": patched_ir,
                "gurobi_code": str(model_dir / "gurobi_model.py"),
                "gurobi_result": solver["patched"]["gurobi"],
                "claim_to_model_mapping": gold["claim_to_model_mapping"],
                "usage": {"fixture": True},
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(rows), "fixture_only": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
