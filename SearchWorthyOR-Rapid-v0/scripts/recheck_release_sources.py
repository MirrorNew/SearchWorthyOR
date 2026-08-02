from __future__ import annotations

import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fitz
import requests
from bs4 import BeautifulSoup

from source_contract import expected_receipt_binding, load_source_catalog, official_host, resolve_source_binding


def default_output_path(root: Path, batch: int | None) -> Path:
    if batch is None:
        return root / "private" / "source_recheck.jsonl"
    return root / "batches" / f"batch_{batch:02d}" / "private" / "source_recheck.jsonl"


def normalize_bytes(payload: bytes, mime: str, url: str) -> str:
    if "pdf" in mime.casefold() or url.casefold().split("?")[0].endswith(".pdf"):
        document = fitz.open(stream=payload, filetype="pdf")
        text = " ".join(page.get_text("text") for page in document)
    else:
        soup = BeautifulSoup(payload, "html.parser")
        for node in soup(["script", "style", "noscript"]):
            node.decompose()
        text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def check(row: dict[str, Any], allowed_hosts: set[str], metadata_errors: list[str]) -> dict[str, Any]:
    observed = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    headers = {"User-Agent": "SearchWorthyOR-Rapid-v0/0.1 release-source-check"}
    try:
        response = requests.get(row["final_url"], headers=headers, timeout=35, allow_redirects=True)
        payload = response.content
        mime = response.headers.get("content-type", "")
        text = normalize_bytes(payload, mime, response.url) if response.status_code == 200 else ""
        excerpt = normalize_text(row["support_excerpt"])
        excerpt_found = bool(excerpt) and excerpt in normalize_text(text)
        redirect_host_allowed = official_host(response.url) in allowed_hosts
        error = None if redirect_host_allowed else f"redirect_host_not_approved:{official_host(response.url)}"
    except Exception as exc:
        response = None
        payload = b""
        mime = ""
        text = ""
        excerpt_found = False
        redirect_host_allowed = False
        error = f"{type(exc).__name__}:{exc}"
    status_code = response.status_code if response is not None else None
    binding = expected_receipt_binding(row)
    return {
        **binding,
        "id": row["id"],
        "requested_url": row["final_url"],
        "final_url": response.url if response is not None else None,
        "accessed_at": observed,
        "http_status": status_code,
        "mime_type": mime,
        "content_sha256": hashlib.sha256(payload).hexdigest() if payload else None,
        "normalized_chars": len(text),
        "support_excerpt_found": excerpt_found,
        "status": "PASS" if status_code == 200 and excerpt_found and redirect_host_allowed and not metadata_errors else "FAIL",
        "error": ";".join([*metadata_errors, *([error] if error else [])]) or None,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rapid-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--batch", type=int, choices=range(1, 6))
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    root = args.rapid_root.resolve()
    primary_by_task, candidate_by_id, reservations_by_task = load_source_catalog(root)
    audits: list[dict[str, Any]] = []
    batches = [args.batch] if args.batch is not None else range(1, 6)
    for batch in batches:
        audits.extend(read_jsonl(root / "batches" / f"batch_{batch:02d}" / "private" / "rapid_audit.jsonl"))
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {}
        for row in audits:
            metadata_errors, allowed_hosts = resolve_source_binding(
                row, primary_by_task, candidate_by_id, reservations_by_task
            )
            futures[pool.submit(check, row, allowed_hosts, metadata_errors)] = row["id"]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda row: row["id"])
    if args.output is not None:
        output = args.output
    else:
        output = default_output_path(root, args.batch)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results),
        encoding="utf-8",
        newline="\n",
    )
    failed = [row["id"] for row in results if row["status"] != "PASS"]
    print(json.dumps({"checked": len(results), "passed": len(results) - len(failed), "failed": failed}, ensure_ascii=False))
    expected = 20 if args.batch is not None else 100
    count_ok = 0 < len(results) <= expected if args.allow_partial else len(results) == expected
    return 0 if not failed and count_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
