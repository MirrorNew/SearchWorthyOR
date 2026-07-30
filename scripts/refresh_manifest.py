"""Refresh manifest hashes after review merge or other authorized artifact updates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_dataset import read_jsonl, refresh_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    root = args.root.resolve()
    gold = read_jsonl(root / "private" / "gold.jsonl")
    summary = {
        "tasks": len(read_jsonl(root / "public" / "tasks_zh.jsonl")),
        "gold_rows": len(gold),
        "unique_base_ids": len({row["base_id"] for row in gold}),
        "evidence_documents": len(
            read_jsonl(root / "private" / "evidence_corpus.jsonl")
        ),
        "all_decision_certificates_pass": all(
            row["decision_certificate"]["passed"] for row in gold
        ),
        "reviews_pending": any(
            row["adjudication"].get("unresolved", True) for row in gold
        ),
    }
    manifest = refresh_manifest(root, summary)
    print(
        json.dumps(
            {"files": len(manifest["files"]), "summary": summary},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

