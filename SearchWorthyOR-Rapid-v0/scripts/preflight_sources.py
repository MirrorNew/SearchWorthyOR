from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fitz
import requests
from bs4 import BeautifulSoup


def normalize(payload: bytes, mime: str, url: str) -> str:
    if "pdf" in mime.casefold() or url.casefold().split("?")[0].endswith(".pdf"):
        document = fitz.open(stream=payload, filetype="pdf")
        text = " ".join(page.get_text("text") for page in document)
    else:
        soup = BeautifulSoup(payload, "html.parser")
        for node in soup(["script", "style", "noscript"]):
            node.decompose()
        text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def locate(text: str, needles: list[str]) -> tuple[bool, list[dict[str, Any]]]:
    folded = text.casefold()
    spans = []
    for needle in needles:
        index = folded.find(needle.casefold())
        found = index >= 0
        spans.append(
            {
                "needle": needle,
                "found": found,
                "excerpt": text[max(0, index - 240): min(len(text), index + len(needle) + 360)] if found else "",
            }
        )
    return all(span["found"] for span in spans), spans


def check(row: dict[str, Any]) -> dict[str, Any]:
    attempts = []
    headers = {"User-Agent": "SearchWorthyOR-Rapid-v0/0.1 current-source-check"}
    for url in [row["primary_url"], *row.get("backup_official_urls", [])]:
        observed = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        try:
            response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
            payload = response.content
            mime = response.headers.get("content-type", "")
            text = normalize(payload, mime, response.url) if response.status_code == 200 else ""
            all_found, spans = locate(text, row["support_needles"]) if text else (False, [])
            attempt = {
                "requested_url": url,
                "final_url": response.url,
                "accessed_at": observed,
                "http_status": response.status_code,
                "mime_type": mime,
                "content_sha256": hashlib.sha256(payload).hexdigest(),
                "normalized_chars": len(text),
                "all_support_needles_found": all_found,
                "support_spans": spans,
                "error": None,
            }
        except Exception as exc:
            attempt = {
                "requested_url": url,
                "final_url": None,
                "accessed_at": observed,
                "http_status": None,
                "mime_type": None,
                "content_sha256": None,
                "normalized_chars": 0,
                "all_support_needles_found": False,
                "support_spans": [],
                "error": f"{type(exc).__name__}:{exc}",
            }
        attempts.append(attempt)
        if attempt["http_status"] == 200 and attempt["all_support_needles_found"]:
            break
    passing = next(
        (attempt for attempt in attempts if attempt["http_status"] == 200 and attempt["all_support_needles_found"]),
        None,
    )
    return {
        "schema_version": "searchworthyor.rapid_source_preflight.v0",
        "batch": row["batch"],
        "shortlist_role": row["shortlist_role"],
        "rapid_task_id": row["rapid_task_id"],
        "source_candidate_id": row["source_candidate_id"],
        "source_document_key": row["source_document_key"],
        "regulation_key": row["regulation_key"],
        "status": "CURRENT_ACCESS_AND_SUPPORT_PASS" if passing else "NEEDS_REPAIR_OR_REPLACEMENT",
        "selected_attempt": passing,
        "attempts": attempts,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shortlist", type=Path, required=True)
    parser.add_argument("--batch", type=int, required=True, choices=range(1, 6))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [
        json.loads(line)
        for line in args.shortlist.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selected = [row for row in rows if row["batch"] == args.batch]
    results = [check(row) for row in selected]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results),
        encoding="utf-8", newline="\n",
    )
    print(
        json.dumps(
            {
                "batch": args.batch,
                "checked": len(results),
                "passed": sum(row["status"] == "CURRENT_ACCESS_AND_SUPPORT_PASS" for row in results),
                "failed": [row["source_candidate_id"] for row in results if row["status"] != "CURRENT_ACCESS_AND_SUPPORT_PASS"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
