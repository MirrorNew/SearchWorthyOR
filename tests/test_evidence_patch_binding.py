"""Regression checks for evidence -> fact -> patch binding."""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from audit_evidence_patch_binding import audit_binding_records  # noqa: E402


def fixture():
    public = [
        {
            "id": "SWOR001",
            "problem_zh": "方案A的本地属性为连续驾驶11.5小时。请检索适用规则。",
        }
    ]
    mapping = {
        "claim_id": "CLAIM-1",
        "claim_zh": "方案A不得采用。",
        "external_rule_zh": "适用规则规定驾驶上限。",
        "derived_model_claim_zh": "方案A不得采用。",
        "derivation_kind": "official_rule_combined_with_public_local_facts",
        "local_binding_zh": "方案A不得采用。",
        "operative_support_excerpt": "maximum of 11 hours",
        "operative_support_excerpts": ["maximum of 11 hours"],
        "local_facts": [
            {"item": "方案A", "policy_attribute": "连续驾驶11.5小时"}
        ],
        "model_slots": ["variables/x/domain"],
        "equations": ["x = 0"],
        "code_regions": ["patched_ir.json#/variables/x"],
    }
    gold = [
        {
            "id": "SWOR001",
            "evidence_mode": "real-web",
            "evidence_ids": ["WEB-1"],
            "claim_to_model_mapping": [mapping],
            "applicability": {"decision_time": "2026-06-15"},
            "typed_patch": {
                "structural": True,
                "pure_numeric_parameter_fill": False,
                "ops": [
                    {
                        "slot_type": "variable_domain",
                        "model_slot_id": "variables/x/domain",
                        "after_expression": "x = 0",
                        "code_region_id": "patched_ir.json#/variables/x",
                        "evidence_claim_id": "CLAIM-1",
                    }
                ],
            },
        }
    ]
    evidence = [
        {
            "id": "WEB-1",
            "content": "冻结支持片段：maximum of 11 hours。",
            "snapshot_ref": "SNAP-1",
            "source_passport": {
                "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-06-15/title-49.xml?part=395&section=395.3",
                "version": "ecfr-point-in-time-2026-06-15",
                "issued_at": "2026-06-15",
                "issued_at_kind": "ecfr_point_in_time_edition_date",
                "effective_from": "2026-06-15",
                "effective_to": "2026-06-15",
                "effective_from_basis": "point-in-time edition",
                "effective_interval_kind": "exact_point_in_time_edition",
                "snapshot_sha256": "a" * 64,
                "snapshot_sha256_kind": "exact_http_response_bytes",
                "raw_content_sha256": "a" * 64,
                "fetched_at": "2026-07-30T00:00:00+00:00",
                "verified_as_of": "2026-07-30",
                "support_text_normalization": "html_entity_unescape+unicode_quote_dash_fold+whitespace_collapse+casefold",
            },
        }
    ]
    snapshots = [
        {
            "snapshot_id": "SNAP-1",
            "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-06-15/title-49.xml?part=395&section=395.3",
            "final_url": "https://www.ecfr.gov/api/versioner/v1/full/2026-06-15/title-49.xml?part=395&section=395.3",
            "support_excerpt": "maximum of 11 hours",
            "support_excerpts": ["maximum of 11 hours"],
            "support_excerpt_verified_in_normalized_dom_text": True,
            "support_text_normalization": "html_entity_unescape+unicode_quote_dash_fold+whitespace_collapse+casefold",
            "status_code": 200,
            "fetched_at": "2026-07-30T00:00:00+00:00",
            "fetched_at_kind": "actual_http_get_timestamp",
            "verified_as_of": "2026-07-30",
            "raw_path": "private/web_snapshots/raw/example.xml",
            "raw_content_sha256": "a" * 64,
            "snapshot_sha256": "a" * 64,
            "snapshot_sha256_kind": "exact_http_response_bytes",
            "source_version": "ecfr-point-in-time-2026-06-15",
            "source_version_date": "2026-06-15",
            "source_version_date_kind": "ecfr_point_in_time_edition_date",
            "effective_from": "2026-06-15",
            "effective_to": "2026-06-15",
            "effective_from_basis": "point-in-time edition",
            "effective_interval_kind": "exact_point_in_time_edition",
        }
    ]
    return public, gold, evidence, snapshots


def codes(report):
    return {entry.code for entry in report.errors}


def test_complete_web_binding_passes():
    assert audit_binding_records(*fixture()).ok


def test_whole_combination_local_fact_is_recoverable():
    public, gold, evidence, snapshots = fixture()
    fact = "本规划期固定包含同一主体的完整决策窗口。"
    public[0]["problem_zh"] += fact
    gold[0]["claim_to_model_mapping"][0]["local_facts"].append(
        {"scope": "whole_combination", "fact_zh": fact}
    )

    assert audit_binding_records(public, gold, evidence, snapshots).ok


def test_public_gold_claim_is_rejected():
    public, gold, evidence, snapshots = fixture()
    public[0]["problem_zh"] += "方案A不得采用。"
    report = audit_binding_records(public, gold, evidence, snapshots)
    assert "binding.gold_claim_public" in codes(report)


def test_unbound_op_and_snapshot_drift_are_rejected():
    public, gold, evidence, snapshots = fixture()
    gold[0]["typed_patch"]["ops"][0]["evidence_claim_id"] = "OTHER"
    snapshots[0]["support_excerpt"] = "different"
    report = audit_binding_records(public, gold, evidence, snapshots)
    assert "binding.op_claim_mismatch" in codes(report)
    assert "binding.web_snapshot_mismatch" in codes(report)


def test_accepts_only_publicly_recoverable_local_facts():
    public, gold, evidence, snapshots = fixture()
    altered = deepcopy(gold)
    altered[0]["claim_to_model_mapping"][0]["local_facts"][0][
        "policy_attribute"
    ] = "隐藏事实"
    report = audit_binding_records(public, altered, evidence, snapshots)
    assert "binding.local_fact_not_public" in codes(report)


def test_current_ecfr_page_is_rejected():
    public, gold, evidence, snapshots = fixture()
    current = "https://www.ecfr.gov/current/title-49/part-395"
    evidence[0]["source_passport"]["url"] = current
    snapshots[0]["url"] = current
    snapshots[0]["final_url"] = current
    report = audit_binding_records(public, gold, evidence, snapshots)
    assert "binding.web_ecfr_not_point_in_time" in codes(report)


def test_decision_date_cannot_masquerade_as_non_ecfr_issue_date():
    public, gold, evidence, snapshots = fixture()
    evidence[0]["source_passport"]["issued_at_kind"] = "official_page_last_updated"
    snapshots[0]["source_version_date_kind"] = "official_page_last_updated"
    report = audit_binding_records(public, gold, evidence, snapshots)
    assert "binding.web_decision_date_as_issue_date" in codes(report)


def test_raw_snapshot_hash_binding_is_required():
    public, gold, evidence, snapshots = fixture()
    snapshots[0]["raw_content_sha256"] = "b" * 64
    report = audit_binding_records(public, gold, evidence, snapshots)
    assert "binding.web_raw_snapshot_incomplete" in codes(report)
    assert "binding.web_passport_raw_snapshot_mismatch" in codes(report)
