#!/usr/bin/env python3
"""Relink frozen web-fetch provenance after deterministic public-ID changes.

This script never accesses the network and never changes raw response bytes,
URLs, fetch timestamps, headers, support excerpts, or raw-content hashes. It
updates only the task-level provenance ID and the manifest metadata hash that
commits to that ID.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from build_dataset import public_task_id, sha256_json


ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def main() -> int:
    blueprint_path = ROOT / "staging" / "evidence_blueprints.jsonl"
    manifest_path = (
        ROOT / "private" / "web_snapshots" / "fetch_manifest.jsonl"
    )
    blueprints = read_jsonl(blueprint_path)
    task_by_url = {
        str(row["web_source_url"]): public_task_id(index)
        for index, row in enumerate(blueprints)
        if row.get("web_source_url")
    }
    if len(task_by_url) != 20:
        raise ValueError(
            f"expected 20 unique web blueprint URLs, found {len(task_by_url)}"
        )

    rows = read_jsonl(manifest_path)
    if len(rows) != 20:
        raise ValueError(f"expected 20 fetch rows, found {len(rows)}")
    seen_urls: set[str] = set()
    changed = 0
    for row in rows:
        url = str(row.get("requested_url"))
        if url not in task_by_url:
            raise ValueError(f"fetch URL is absent from blueprints: {url}")
        if url in seen_urls:
            raise ValueError(f"duplicate fetch URL: {url}")
        seen_urls.add(url)
        new_task_id = task_by_url[url]
        changed += row.get("task_id") != new_task_id
        row["task_id"] = new_task_id
        row["metadata_sha256"] = sha256_json(
            {
                key: value
                for key, value in row.items()
                if key != "metadata_sha256"
            }
        )

    if seen_urls != set(task_by_url):
        raise ValueError("fetch manifest and blueprint URL sets differ")
    write_jsonl(manifest_path, rows)
    print(
        json.dumps(
            {
                "status": "RELINKED",
                "rows": len(rows),
                "task_ids_changed": changed,
                "network_accessed": False,
                "raw_bytes_changed": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
