#!/usr/bin/env python3
"""Fetch and freeze the 20 official web responses used by SearchWorthyOR-100.

The fetch manifest records hashes of the exact HTTP response bytes.  It is a
separate artifact from the hand-curated temporal/applicability passport: a hash
of metadata is never presented as a hash of an official page.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from pypdf import PdfReader

from build_dataset import WEB_SUPPORT_FRAGMENTS, public_task_id, web_support_fragments


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINTS = ROOT / "staging" / "evidence_blueprints.jsonl"
MANIFEST = ROOT / "private" / "web_snapshots" / "fetch_manifest.jsonl"
RAW_DIR = ROOT / "private" / "web_snapshots" / "raw"
SUPPORT_TEXT_NORMALIZATION = (
    "html_entity_unescape+unicode_quote_dash_fold+whitespace_collapse+casefold"
)

OFFICIAL_HOSTS = {
    "app.leg.wa.gov",
    "www.dir.ca.gov",
    "www.ecfr.gov",
    "www.epa.gov",
    "www.fda.gov",
    "www.fmcsa.dot.gov",
    "www.irs.gov",
}


class VisibleTextParser(HTMLParser):
    """Small dependency-free visible-text extractor for excerpt verification."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._ignored_depth = max(0, self._ignored_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0:
            self.parts.append(data)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def normalize_text(value: str) -> str:
    value = html.unescape(value).replace("\u00a0", " ")
    value = (
        value.replace("\u2010", "-")
        .replace("\u2011", "-")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2212", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )
    return re.sub(r"\s+", " ", value).strip().casefold()


def response_text(raw: bytes, encoding: str | None, content_type: str) -> str:
    if "pdf" in content_type.casefold():
        return "\n".join(
            page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages
        )
    if not any(kind in content_type.casefold() for kind in ("html", "xml")):
        return raw.decode(encoding or "utf-8", errors="replace")
    decoded = raw.decode(encoding or "utf-8", errors="replace")
    parser = VisibleTextParser()
    parser.feed(decoded)
    parser.close()
    return " ".join(parser.parts)


def response_encoding(
    raw: bytes, reported_encoding: str | None, content_type: str
) -> str:
    if "xml" in content_type.casefold():
        declaration = re.match(
            br"\s*<\?xml[^>]*encoding=[\"']([^\"']+)[\"']", raw[:256], re.I
        )
        if declaration:
            return declaration.group(1).decode("ascii", errors="replace")
        return "utf-8"
    return reported_encoding or "utf-8"


def manifest_metadata_hash(row: dict[str, Any]) -> str:
    payload = {key: value for key, value in row.items() if key != "metadata_sha256"}
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def collect_sources(blueprints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(blueprints, start=1):
        if row.get("evidence_mode") != "real-web":
            continue
        url = str(row["web_source_url"])
        sources[url] = {
            "requested_url": url,
            "task_id": public_task_id(index - 1),
            "decision_time": row["decision_time"],
            "source_topic": row["applicable_policy_blueprint"]["source_topic"],
            "support_excerpt": WEB_SUPPORT_FRAGMENTS[url],
            "support_excerpts": web_support_fragments(url),
        }
    return [sources[url] for url in sorted(sources)]


def fetch_one(session: requests.Session, source: dict[str, Any]) -> dict[str, Any]:
    requested_url = source["requested_url"]
    requested_host = (urlparse(requested_url).hostname or "").lower()
    if requested_host not in OFFICIAL_HOSTS:
        raise ValueError(f"requested URL is not on the official allowlist: {requested_url}")
    response = session.get(requested_url, timeout=(15, 90), allow_redirects=True)
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {requested_url}")
    final_url = response.url
    final_host = (urlparse(final_url).hostname or "").lower()
    if urlparse(final_url).scheme != "https" or final_host not in OFFICIAL_HOSTS:
        raise ValueError(f"redirect left the official HTTPS allowlist: {final_url}")

    raw = response.content
    raw_sha256 = hashlib.sha256(raw).hexdigest()
    content_type = response.headers.get("content-type", "")
    encoding = response_encoding(raw, response.encoding, content_type)
    visible = normalize_text(response_text(raw, encoding, content_type))
    for fragment in source["support_excerpts"]:
        expected = normalize_text(fragment)
        if expected not in visible:
            raise ValueError(
                f"support excerpt not found in official response for {source['task_id']}: "
                f"{fragment!r}"
            )

    suffix = (
        ".pdf"
        if "pdf" in content_type.casefold()
        else ".html"
        if "html" in content_type.casefold()
        else ".response"
    )
    raw_name = f"{hashlib.sha256(requested_url.encode('utf-8')).hexdigest()}{suffix}"
    raw_path = RAW_DIR / raw_name
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(raw)
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    row = {
        **source,
        "final_url": final_url,
        "status_code": response.status_code,
        "fetched_at": fetched_at,
        "fetch_kind": "actual_http_get",
        "response_headers": {
            key.lower(): value
            for key, value in response.headers.items()
            if key.lower() in {"content-type", "date", "etag", "last-modified"}
        },
        "content_type": content_type,
        "text_encoding": encoding,
        "raw_content_sha256": raw_sha256,
        "raw_size_bytes": len(raw),
        "raw_path": raw_path.relative_to(ROOT).as_posix(),
        "support_excerpt_verified_in_normalized_dom_text": True,
        "support_text_normalization": SUPPORT_TEXT_NORMALIZATION,
        "verified_as_of": fetched_at[:10],
    }
    row["metadata_sha256"] = manifest_metadata_hash(row)
    return row


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
        encoding="utf-8",
    )


def main() -> int:
    global ROOT, BLUEPRINTS, MANIFEST, RAW_DIR
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    ROOT = root
    BLUEPRINTS = root / "staging" / "evidence_blueprints.jsonl"
    MANIFEST = root / "private" / "web_snapshots" / "fetch_manifest.jsonl"
    RAW_DIR = root / "private" / "web_snapshots" / "raw"

    sources = collect_sources(read_jsonl(BLUEPRINTS))
    if len(sources) != 20:
        raise ValueError(f"expected 20 unique official web sources, found {len(sources)}")
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/138.0.0.0 Safari/537.36 "
                "SearchWorthyOR-100-Academic-Evidence-Freezer"
            ),
            "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
        }
    )
    rows = [fetch_one(session, source) for source in sources]
    write_jsonl(MANIFEST, rows)
    print(
        json.dumps(
            {
                "status": "FETCHED",
                "sources": len(rows),
                "all_http_200": all(row["status_code"] == 200 for row in rows),
                "all_excerpts_verified": all(
                    row["support_excerpt_verified_in_normalized_dom_text"]
                    for row in rows
                ),
                "manifest": str(MANIFEST),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
