from __future__ import annotations

import argparse
import collections
import json
import math
import re
from pathlib import Path
from typing import Any


LATIN_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-._/][a-z0-9]+)*", re.IGNORECASE)
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def tokenize(text: str) -> list[str]:
    lowered = text.casefold()
    tokens = LATIN_TOKEN_RE.findall(lowered)
    for chunk in CJK_RE.findall(lowered):
        tokens.extend(chunk)
        tokens.extend(chunk[index : index + 2] for index in range(len(chunk) - 1))
    return tokens


class FrozenBM25:
    def __init__(self, documents: list[dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.documents = documents
        self.k1 = k1
        self.b = b
        self.term_frequencies = [
            collections.Counter(tokenize(document["content"])) for document in documents
        ]
        self.lengths = [sum(counter.values()) for counter in self.term_frequencies]
        self.average_length = sum(self.lengths) / max(len(self.lengths), 1)
        document_frequency: collections.Counter[str] = collections.Counter()
        for counter in self.term_frequencies:
            document_frequency.update(counter.keys())
        total = len(documents)
        self.idf = {
            token: math.log(1.0 + (total - frequency + 0.5) / (frequency + 0.5))
            for token, frequency in document_frequency.items()
        }

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        query_terms = collections.Counter(tokenize(query))
        rows = []
        for document, frequencies, length in zip(
            self.documents, self.term_frequencies, self.lengths, strict=True
        ):
            score = 0.0
            for token, query_count in query_terms.items():
                frequency = frequencies.get(token, 0)
                if not frequency:
                    continue
                denominator = frequency + self.k1 * (
                    1.0 - self.b + self.b * length / max(self.average_length, 1e-12)
                )
                score += (
                    self.idf.get(token, 0.0)
                    * frequency
                    * (self.k1 + 1.0)
                    / denominator
                    * query_count
                )
            rows.append(
                {
                    "id": document["id"],
                    "score": score,
                    "source_kind": document.get("source_kind"),
                    "content": document["content"],
                    "content_sha256": document.get("content_sha256"),
                }
            )
        rows.sort(key=lambda row: (-row["score"], row["id"]))
        return rows[:top_k]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Search the frozen evidence corpus without using Gold mappings."
    )
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--ids-only", action="store_true")
    args = parser.parse_args()

    documents = read_jsonl(args.corpus)
    results = FrozenBM25(documents).search(args.query, args.top_k)
    if args.ids_only:
        results = [
            {"rank": rank, "id": row["id"], "score": row["score"]}
            for rank, row in enumerate(results, 1)
        ]
    else:
        for rank, row in enumerate(results, 1):
            row["rank"] = rank
    print(json.dumps({"query": args.query, "results": results}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
