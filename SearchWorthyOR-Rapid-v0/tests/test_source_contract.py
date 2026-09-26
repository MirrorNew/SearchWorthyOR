from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from source_contract import (
    canonical_url,
    expected_receipt_binding,
    official_host,
    receipt_binding_errors,
    resolve_source_binding,
)


def test_url_helpers_reject_missing_receipt_urls_without_crashing() -> None:
    assert canonical_url(None) == ""
    assert official_host(None) == ""


def _primary() -> dict:
    return {
        "rapid_task_id": "SWOR-R001",
        "source_candidate_id": "SRCV2-0001",
        "shortlist_role": "PRIMARY",
        "assigned_family": "routing_transport",
        "assigned_patch_class": "eligibility_domain",
        "source_document_key": "DOC-1",
        "regulation_key": "RULE-1",
        "authority": "Example Authority",
        "jurisdiction": "Example Jurisdiction",
        "primary_url": "https://agency.example/rule",
        "backup_official_urls": ["https://docs.agency.example/rule.pdf"],
    }


def _audit() -> dict:
    return {
        "id": "SWOR-R001",
        "source_candidate_id": "SRCV2-0001",
        "source_document_key": "DOC-1",
        "regulation_key": "RULE-1",
        "authority": "Example Authority",
        "jurisdiction": "Example Jurisdiction",
        "source_url": "https://agency.example/rule",
        "final_url": "https://agency.example/rule",
        "support_excerpt": "A sufficiently specific official support excerpt.",
        "family": "routing_transport",
        "patch_class": "eligibility_domain",
    }


def test_primary_metadata_and_receipt_are_bound_to_current_audit() -> None:
    primary = _primary()
    audit = _audit()
    errors, hosts = resolve_source_binding(
        audit, {audit["id"]: primary}, {primary["source_candidate_id"]: primary}, {}
    )
    assert errors == []
    assert hosts == {"agency.example", "docs.agency.example"}
    receipt = {**expected_receipt_binding(audit), "status": "PASS"}
    assert receipt_binding_errors(audit, receipt) == []
    audit["support_excerpt"] = "A changed official support excerpt that must invalidate the receipt."
    assert receipt_binding_errors(audit, receipt) == ["support_excerpt_sha256"]


def test_replacement_cannot_change_primary_quota_labels_and_needs_metadata() -> None:
    primary = _primary()
    audit = _audit()
    audit["source_candidate_id"] = "LOCAL-REPLACEMENT"
    reservation = {
        "rapid_task_id": audit["id"],
        "replacement_source_candidate_id": "LOCAL-REPLACEMENT",
        "replacement_supports_assigned_family": primary["assigned_family"],
        "replacement_supports_assigned_patch_class": primary["assigned_patch_class"],
        "status": "RESERVED_CURRENT_ACCESS_AND_SUPPORT_PASS",
    }
    errors, _ = resolve_source_binding(
        audit, {audit["id"]: primary}, {primary["source_candidate_id"]: primary}, {audit["id"]: [reservation]}
    )
    assert any(error.startswith("replacement_metadata_incomplete:") for error in errors)
    audit["family"] = "telecom_service"
    errors, _ = resolve_source_binding(
        audit, {audit["id"]: primary}, {primary["source_candidate_id"]: primary}, {audit["id"]: [reservation]}
    )
    assert "family_not_primary_assignment" in errors
