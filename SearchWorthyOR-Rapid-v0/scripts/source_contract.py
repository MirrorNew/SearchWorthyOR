from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


REPLACEMENT_METADATA_FIELDS = {
    "source_document_key": "replacement_source_document_key",
    "regulation_key": "replacement_regulation_key",
    "authority": "replacement_authority",
    "jurisdiction": "replacement_jurisdiction",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def canonical_url(url: str) -> str:
    if not isinstance(url, str):
        return ""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), parts.path.rstrip("/"), parts.query, ""))


def official_host(url: str) -> str:
    if not isinstance(url, str):
        return ""
    parts = urlsplit(url)
    return (parts.hostname or "").casefold() if parts.scheme.casefold() == "https" else ""


def normalized_excerpt_sha256(excerpt: str) -> str:
    normalized = re.sub(r"\s+", " ", excerpt).strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def load_source_catalog(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    shortlist = read_jsonl(root / "private" / "source_shortlist_130.jsonl")
    primary_by_task: dict[str, dict[str, Any]] = {}
    candidate_by_id: dict[str, dict[str, Any]] = {}
    for row in shortlist:
        candidate_id = row["source_candidate_id"]
        if candidate_id in candidate_by_id:
            raise ValueError(f"duplicate shortlist candidate: {candidate_id}")
        candidate_by_id[candidate_id] = row
        if row.get("shortlist_role") == "PRIMARY":
            task_id = row.get("rapid_task_id")
            if task_id in primary_by_task:
                raise ValueError(f"duplicate PRIMARY assignment: {task_id}")
            primary_by_task[task_id] = row
    reservations_by_task: dict[str, list[dict[str, Any]]] = {}
    for row in read_jsonl(root / "private" / "replacement_reservations.jsonl"):
        reservations_by_task.setdefault(row.get("rapid_task_id"), []).append(row)
    return primary_by_task, candidate_by_id, reservations_by_task


def resolve_source_binding(
    audit: dict[str, Any],
    primary_by_task: dict[str, dict[str, Any]],
    candidate_by_id: dict[str, dict[str, Any]],
    reservations_by_task: dict[str, list[dict[str, Any]]],
) -> tuple[list[str], set[str]]:
    task_id = audit.get("id")
    errors: list[str] = []
    primary = primary_by_task.get(task_id)
    if primary is None:
        return ["primary_source_assignment_missing"], set()
    if audit.get("family") != primary.get("assigned_family"):
        errors.append("family_not_primary_assignment")
    if audit.get("patch_class") != primary.get("assigned_patch_class"):
        errors.append("patch_class_not_primary_assignment")

    candidate_id = audit.get("source_candidate_id")
    metadata: dict[str, Any] | None = None
    approved_urls: list[str] = []
    if candidate_id == primary.get("source_candidate_id"):
        metadata = primary
        approved_urls = [primary["primary_url"], *primary.get("backup_official_urls", [])]
    else:
        matches = [
            row for row in reservations_by_task.get(task_id, [])
            if row.get("replacement_source_candidate_id") == candidate_id
        ]
        if len(matches) != 1:
            errors.append("replacement_reservation_missing_or_ambiguous")
        else:
            reservation = matches[0]
            if reservation.get("status") != "RESERVED_CURRENT_ACCESS_AND_SUPPORT_PASS":
                errors.append("replacement_not_current_pass")
            if reservation.get("replacement_supports_assigned_family") != primary.get("assigned_family"):
                errors.append("replacement_changes_family_assignment")
            if reservation.get("replacement_supports_assigned_patch_class") != primary.get("assigned_patch_class"):
                errors.append("replacement_changes_patch_class_assignment")
            metadata = candidate_by_id.get(candidate_id)
            if metadata is not None:
                approved_urls = [metadata["primary_url"], *metadata.get("backup_official_urls", [])]
            else:
                missing = [field for field in REPLACEMENT_METADATA_FIELDS.values() if not reservation.get(field)]
                urls = reservation.get("replacement_official_urls")
                if not isinstance(urls, list) or not urls:
                    missing.append("replacement_official_urls")
                if missing:
                    errors.append(f"replacement_metadata_incomplete:{','.join(sorted(missing))}")
                else:
                    metadata = {
                        audit_field: reservation[reservation_field]
                        for audit_field, reservation_field in REPLACEMENT_METADATA_FIELDS.items()
                    }
                    approved_urls = urls

    allowed_hosts = {official_host(url) for url in approved_urls}
    if "" in allowed_hosts:
        errors.append("approved_source_url_not_https")
        allowed_hosts.discard("")
    if metadata is not None:
        for field in REPLACEMENT_METADATA_FIELDS:
            if audit.get(field) != metadata.get(field):
                errors.append(f"{field}_not_source_metadata")
    approved_canonical = {canonical_url(url) for url in approved_urls}
    if canonical_url(audit.get("source_url", "")) not in approved_canonical:
        errors.append("source_url_not_approved")
    if official_host(audit.get("final_url", "")) not in allowed_hosts:
        errors.append("final_url_host_not_approved")
    return errors, allowed_hosts


def expected_receipt_binding(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": audit["id"],
        "requested_url": audit["final_url"],
        "source_candidate_id": audit["source_candidate_id"],
        "source_document_key": audit["source_document_key"],
        "regulation_key": audit["regulation_key"],
        "support_excerpt_sha256": normalized_excerpt_sha256(audit["support_excerpt"]),
    }


def receipt_binding_errors(audit: dict[str, Any], receipt: dict[str, Any]) -> list[str]:
    expected = expected_receipt_binding(audit)
    return [field for field, value in expected.items() if receipt.get(field) != value]
