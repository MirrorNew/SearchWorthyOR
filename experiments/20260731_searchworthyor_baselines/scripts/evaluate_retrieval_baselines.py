from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_dataset import queryless_majority_choice, queryless_medoid_choice
from controlled_retrieval import FrozenBM25, read_jsonl


def reciprocal_rank(ranked_ids: list[str], target: str) -> float:
    try:
        return 1.0 / (ranked_ids.index(target) + 1)
    except ValueError:
        return 0.0


def evaluate_query(
    index: FrozenBM25,
    query: str,
    target: str,
    top_k: int,
) -> dict[str, Any]:
    results = index.search(query, top_k)
    ranked_ids = [row["id"] for row in results]
    rank = ranked_ids.index(target) + 1 if target in ranked_ids else None
    return {
        "query": query,
        "rank": rank,
        "hit_at_1": rank == 1,
        "hit_at_5": rank is not None and rank <= 5,
        "hit_at_10": rank is not None and rank <= 10,
        "reciprocal_rank": reciprocal_rank(ranked_ids, target),
        "top_ids": ranked_ids[:10],
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "n": len(rows),
        "hit_at_1": sum(row["hit_at_1"] for row in rows) / len(rows),
        "hit_at_5": sum(row["hit_at_5"] for row in rows) / len(rows),
        "hit_at_10": sum(row["hit_at_10"] for row in rows) / len(rows),
        "mrr_at_100": sum(row["reciprocal_rank"] for row in rows) / len(rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    tasks = read_jsonl(args.dataset_root / "public" / "tasks_zh.jsonl")
    gold = read_jsonl(args.dataset_root / "private" / "gold.jsonl")
    evidence = read_jsonl(args.dataset_root / "private" / "evidence_corpus.jsonl")
    gold_by_id = {row["id"]: row for row in gold}
    index = FrozenBM25(evidence)

    rows = []
    for task in tasks:
        target = gold_by_id[task["id"]]["applicability"]["selected_evidence_id"]
        full = evaluate_query(index, task["problem_zh"], target, len(evidence))
        metadata_query = " ".join(
            [
                task["entity"],
                task["jurisdiction"],
                task["decision_time"],
            ]
        )
        metadata = evaluate_query(index, metadata_query, target, len(evidence))
        metadata_top5_documents = index.search(metadata_query, 5)
        metadata_top5_medoid = queryless_medoid_choice(metadata_top5_documents)
        metadata_top5_majority = queryless_majority_choice(metadata_top5_documents)
        rows.append(
            {
                "id": task["id"],
                "evidence_mode": gold_by_id[task["id"]]["evidence_mode"],
                "family": gold_by_id[task["id"]]["family"],
                "full_problem": full,
                "metadata_only": metadata,
                "metadata_top5_medoid": {
                    "selected_id": metadata_top5_medoid,
                    "correct": metadata_top5_medoid == target,
                },
                "metadata_top5_majority": {
                    "selected_id": metadata_top5_majority,
                    "correct": metadata_top5_majority == target,
                },
            }
        )

    output = {
        "full_problem": aggregate([row["full_problem"] for row in rows]),
        "metadata_only": aggregate([row["metadata_only"] for row in rows]),
        "metadata_top5_medoid_accuracy": sum(
            row["metadata_top5_medoid"]["correct"] for row in rows
        )
        / len(rows),
        "metadata_top5_majority_accuracy": sum(
            row["metadata_top5_majority"]["correct"] for row in rows
        )
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
            {
                "full_problem": output["full_problem"],
                "metadata_only": output["metadata_only"],
                "metadata_top5_medoid_accuracy": output[
                    "metadata_top5_medoid_accuracy"
                ],
                "metadata_top5_majority_accuracy": output[
                    "metadata_top5_majority_accuracy"
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
