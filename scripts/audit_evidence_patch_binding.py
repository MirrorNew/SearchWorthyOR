"""Fail-closed audit of evidence -> local facts -> typed model patch bindings."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from fetch_web_snapshots import (
    OFFICIAL_HOSTS,
    SUPPORT_TEXT_NORMALIZATION,
    normalize_text,
    response_text,
)
from validate_dataset_schema import Issue, issue, load_jsonl


ALLOWED_SLOT_TYPES = {
    "variable",
    "variable_domain",
    "constraint",
    "objective_term",
    "index_set",
}


@dataclasses.dataclass
class BindingReport:
    errors: list[Issue] = dataclasses.field(default_factory=list)
    warnings: list[Issue] = dataclasses.field(default_factory=list)
    stats: dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": [entry.as_dict() for entry in self.errors],
            "warnings": [entry.as_dict() for entry in self.warnings],
            "stats": self.stats,
        }


def _records_by_id(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row["id"]): row
        for row in rows
        if isinstance(row.get("id"), str)
    }


def audit_binding_records(
    public_rows: Sequence[Mapping[str, Any]],
    gold_rows: Sequence[Mapping[str, Any]],
    evidence_rows: Sequence[Mapping[str, Any]],
    snapshot_rows: Sequence[Mapping[str, Any]],
    *,
    root: Path | None = None,
    fetch_rows: Sequence[Mapping[str, Any]] = (),
) -> BindingReport:
    report = BindingReport()
    public_by_id = _records_by_id(public_rows)
    evidence_by_id = _records_by_id(evidence_rows)
    snapshots = {
        str(row["snapshot_id"]): row
        for row in snapshot_rows
        if isinstance(row.get("snapshot_id"), str)
    }
    fetches = {
        str(row["requested_url"]): row
        for row in fetch_rows
        if isinstance(row.get("requested_url"), str)
    }
    web_count = 0
    private_count = 0
    for row_index, gold in enumerate(gold_rows, start=1):
        task_id = str(gold.get("id", f"<row-{row_index}>"))
        path = f"private/gold.jsonl:{row_index}"
        public = public_by_id.get(task_id)
        problem = public.get("problem_zh") if isinstance(public, Mapping) else None
        if not isinstance(problem, str):
            report.errors.append(
                issue(
                    "binding.public_problem_missing",
                    f"public/tasks_zh.jsonl[{task_id}]",
                    "public problem is required for evidence binding audit",
                )
            )
            continue
        mappings = gold.get("claim_to_model_mapping")
        if not isinstance(mappings, list) or len(mappings) != 1:
            report.errors.append(
                issue(
                    "binding.mapping_cardinality",
                    f"{path}.claim_to_model_mapping",
                    "exactly one evidence claim mapping is required",
                )
            )
            continue
        mapping = mappings[0]
        if not isinstance(mapping, Mapping):
            report.errors.append(
                issue(
                    "binding.mapping_invalid",
                    f"{path}.claim_to_model_mapping[0]",
                    "claim mapping must be an object",
                )
            )
            continue
        claim_id = mapping.get("claim_id")
        claim = mapping.get("claim_zh")
        external_rule = mapping.get("external_rule_zh")
        derived = mapping.get("derived_model_claim_zh")
        local_binding = mapping.get("local_binding_zh")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (claim_id, claim, external_rule, derived, local_binding)
        ):
            report.errors.append(
                issue(
                    "binding.claim_fields_missing",
                    f"{path}.claim_to_model_mapping[0]",
                    "claim, external rule, derived claim, and local binding are required",
                )
            )
            continue
        if derived != claim or local_binding != claim:
            report.errors.append(
                issue(
                    "binding.derived_claim_mismatch",
                    f"{path}.claim_to_model_mapping[0]",
                    "claim_zh, derived_model_claim_zh, and local_binding_zh must agree",
                )
            )
        if claim in problem:
            report.errors.append(
                issue(
                    "binding.gold_claim_public",
                    f"public/tasks_zh.jsonl[{task_id}].problem_zh",
                    "the derived gold patch claim is already stated in the public task",
                )
            )
        local_facts = mapping.get("local_facts")
        if not isinstance(local_facts, list) or not local_facts:
            report.errors.append(
                issue(
                    "binding.local_facts_missing",
                    f"{path}.claim_to_model_mapping[0].local_facts",
                    "public local facts are required",
                )
            )
        else:
            for fact_index, fact in enumerate(local_facts):
                if not isinstance(fact, Mapping):
                    report.errors.append(
                        issue(
                            "binding.local_fact_invalid",
                            f"{path}.claim_to_model_mapping[0].local_facts[{fact_index}]",
                            "local fact must be an object",
                        )
                    )
                    continue
                item = fact.get("item")
                attribute = fact.get("policy_attribute")
                if fact.get("scope") == "whole_combination":
                    global_fact = fact.get("fact_zh")
                    if isinstance(global_fact, str) and global_fact in problem:
                        continue
                if (
                    not isinstance(item, str)
                    or not isinstance(attribute, str)
                    or item not in problem
                    or attribute not in problem
                ):
                    report.errors.append(
                        issue(
                            "binding.local_fact_not_public",
                            f"{path}.claim_to_model_mapping[0].local_facts[{fact_index}]",
                            "gold local fact is not exactly recoverable from public text",
                        )
                    )
        typed_patch = gold.get("typed_patch")
        ops = typed_patch.get("ops") if isinstance(typed_patch, Mapping) else None
        if (
            not isinstance(typed_patch, Mapping)
            or typed_patch.get("structural") is not True
            or typed_patch.get("pure_numeric_parameter_fill") is not False
            or not isinstance(ops, list)
            or not ops
        ):
            report.errors.append(
                issue(
                    "binding.patch_not_structural",
                    f"{path}.typed_patch",
                    "typed patch must be non-empty, structural, and non-numeric-only",
                )
            )
            continue
        op_slots: list[str] = []
        op_equations: list[Any] = []
        op_regions: list[str] = []
        for op_index, op in enumerate(ops):
            op_path = f"{path}.typed_patch.ops[{op_index}]"
            if not isinstance(op, Mapping):
                report.errors.append(
                    issue("binding.op_invalid", op_path, "patch op must be an object")
                )
                continue
            if op.get("evidence_claim_id") != claim_id:
                report.errors.append(
                    issue(
                        "binding.op_claim_mismatch",
                        f"{op_path}.evidence_claim_id",
                        "patch op is not bound to the sole evidence claim",
                    )
                )
            if op.get("slot_type") not in ALLOWED_SLOT_TYPES:
                report.errors.append(
                    issue(
                        "binding.op_slot_type_invalid",
                        f"{op_path}.slot_type",
                        "patch op does not modify an allowed structural slot",
                    )
                )
            op_slots.append(str(op.get("model_slot_id")))
            op_equations.append(op.get("after_expression"))
            op_regions.append(str(op.get("code_region_id")))
        if mapping.get("model_slots") != op_slots:
            report.errors.append(
                issue(
                    "binding.model_slots_mismatch",
                    f"{path}.claim_to_model_mapping[0].model_slots",
                    "claim model slots differ from typed patch ops",
                )
            )
        if mapping.get("equations") != op_equations:
            report.errors.append(
                issue(
                    "binding.equations_mismatch",
                    f"{path}.claim_to_model_mapping[0].equations",
                    "claim equations differ from typed patch ops",
                )
            )
        if mapping.get("code_regions") != op_regions:
            report.errors.append(
                issue(
                    "binding.code_regions_mismatch",
                    f"{path}.claim_to_model_mapping[0].code_regions",
                    "claim code regions differ from typed patch ops",
                )
            )

        evidence_ids = gold.get("evidence_ids")
        if not isinstance(evidence_ids, list) or len(evidence_ids) != 1:
            report.errors.append(
                issue(
                    "binding.evidence_cardinality",
                    f"{path}.evidence_ids",
                    "exactly one applicable evidence record is required",
                )
            )
            continue
        evidence = evidence_by_id.get(str(evidence_ids[0]))
        if evidence is None:
            report.errors.append(
                issue(
                    "binding.evidence_missing",
                    f"{path}.evidence_ids[0]",
                    "applicable evidence record is missing",
                )
            )
            continue
        evidence_content = evidence.get("content")
        if not isinstance(evidence_content, str):
            evidence_content = ""
        mode = gold.get("evidence_mode")
        if mode == "fresh-private":
            private_count += 1
            if mapping.get("derivation_kind") != "direct_private_clause":
                report.errors.append(
                    issue(
                        "binding.private_derivation_kind",
                        f"{path}.claim_to_model_mapping[0].derivation_kind",
                        "private evidence must be marked direct_private_clause",
                    )
                )
            if claim not in evidence_content:
                report.errors.append(
                    issue(
                        "binding.private_claim_absent",
                        f"private/evidence_corpus.jsonl[{evidence_ids[0]}].content",
                        "private operative claim is absent from evidence text",
                    )
                )
            if mapping.get("operative_support_excerpt") is not None:
                report.errors.append(
                    issue(
                        "binding.private_excerpt_unexpected",
                        f"{path}.claim_to_model_mapping[0].operative_support_excerpt",
                        "private direct clauses do not use a web support excerpt",
                    )
                )
            if mapping.get("operative_support_excerpts") not in (None, []):
                report.errors.append(
                    issue(
                        "binding.private_excerpts_unexpected",
                        f"{path}.claim_to_model_mapping[0].operative_support_excerpts",
                        "private direct clauses do not use web support excerpts",
                    )
                )
            passport = gold.get("source_passport")
            if not isinstance(passport, Mapping) or (
                passport.get("generated_after_base_freeze") is not True
                or passport.get("artifact_generation_order") != "after_base_freeze"
                or not isinstance(passport.get("artifact_generated_at"), str)
                or passport.get("issued_at_kind") != "synthetic_policy_issue_date"
            ):
                report.errors.append(
                    issue(
                        "binding.private_generation_provenance",
                        f"{path}.source_passport",
                        "private evidence must distinguish synthetic policy dates from post-freeze artifact generation",
                    )
                )
        elif mode == "real-web":
            web_count += 1
            if (
                mapping.get("derivation_kind")
                != "official_rule_combined_with_public_local_facts"
            ):
                report.errors.append(
                    issue(
                        "binding.web_derivation_kind",
                        f"{path}.claim_to_model_mapping[0].derivation_kind",
                        "web evidence must explicitly combine official rule and public facts",
                    )
                )
            excerpt = mapping.get("operative_support_excerpt")
            excerpts = mapping.get("operative_support_excerpts")
            if not isinstance(excerpt, str) or not excerpt.strip():
                report.errors.append(
                    issue(
                        "binding.web_excerpt_missing",
                        f"{path}.claim_to_model_mapping[0].operative_support_excerpt",
                        "web task needs a frozen operative support excerpt",
                    )
                )
            elif excerpt not in evidence_content:
                report.errors.append(
                    issue(
                        "binding.web_excerpt_not_in_evidence",
                        f"private/evidence_corpus.jsonl[{evidence_ids[0]}].content",
                        "frozen support excerpt is absent from evidence content",
                    )
                )
            if (
                not isinstance(excerpts, list)
                or not excerpts
                or any(
                    not isinstance(fragment, str) or not fragment.strip()
                    for fragment in excerpts
                )
                or excerpts[0] != excerpt
            ):
                report.errors.append(
                    issue(
                        "binding.web_excerpts_invalid",
                        f"{path}.claim_to_model_mapping[0].operative_support_excerpts",
                        "web task needs an ordered non-empty support excerpt set whose first item is the primary excerpt",
                    )
                )
                excerpts = [excerpt] if isinstance(excerpt, str) else []
            for fragment in excerpts:
                if fragment not in evidence_content:
                    report.errors.append(
                        issue(
                            "binding.web_excerpt_not_in_evidence",
                            f"private/evidence_corpus.jsonl[{evidence_ids[0]}].content",
                            "a frozen support excerpt is absent from evidence content",
                        )
                    )
            evidence_passport = evidence.get("source_passport")
            evidence_passport = (
                evidence_passport
                if isinstance(evidence_passport, Mapping)
                else {}
            )
            gold_passport = gold.get("source_passport")
            gold_passport = (
                gold_passport if isinstance(gold_passport, Mapping) else {}
            )
            passport = (
                dict(gold_passport)
                if gold_passport
                else dict(evidence_passport)
            )
            # Legacy/unit fixtures may provide an explicit private snapshot
            # link.  Released retrieval rows intentionally do not; their
            # private Gold provenance is matched by URL and raw-byte hash.
            snapshot_ref = evidence.get("snapshot_ref")
            if snapshot_ref is None:
                snapshot_ref = next(
                    (
                        candidate_id
                        for candidate_id, candidate in snapshots.items()
                        if candidate.get("url") == passport.get("url")
                        and candidate.get("raw_content_sha256")
                        == passport.get("raw_content_sha256")
                    ),
                    None,
                )
            snapshot = snapshots.get(str(snapshot_ref))
            if snapshot is None:
                report.errors.append(
                    issue(
                        "binding.web_snapshot_missing",
                        f"{path}.source_passport",
                        "Gold web provenance has no matching frozen snapshot",
                    )
                )
            else:
                passport_url = (
                    passport.get("url") if isinstance(passport, Mapping) else None
                )
                if (
                    snapshot.get("support_excerpt") != excerpt
                    or snapshot.get("support_excerpts") != excerpts
                    or snapshot.get("url") != passport_url
                ):
                    report.errors.append(
                        issue(
                            "binding.web_snapshot_mismatch",
                            f"private/web_source_snapshots.jsonl[{snapshot_ref}]",
                            "snapshot excerpt or URL differs from evidence passport",
                        )
                    )
                snapshot_url = str(snapshot.get("url", ""))
                final_url = str(snapshot.get("final_url", ""))
                raw_sha256 = snapshot.get("raw_content_sha256")
                if (
                    snapshot.get("status_code") != 200
                    or snapshot.get("fetched_at_kind")
                    != "actual_http_get_timestamp"
                    or snapshot.get("snapshot_sha256_kind")
                    != "exact_http_response_bytes"
                    or snapshot.get(
                        "support_excerpt_verified_in_normalized_dom_text"
                    )
                    is not True
                    or snapshot.get("support_text_normalization")
                    != SUPPORT_TEXT_NORMALIZATION
                    or not isinstance(raw_sha256, str)
                    or snapshot.get("snapshot_sha256") != raw_sha256
                    or not isinstance(snapshot.get("fetched_at"), str)
                    or not isinstance(snapshot.get("verified_as_of"), str)
                    or not isinstance(snapshot.get("raw_path"), str)
                ):
                    report.errors.append(
                        issue(
                            "binding.web_raw_snapshot_incomplete",
                            f"private/web_source_snapshots.jsonl[{snapshot_ref}]",
                            "web snapshot must identify a successful actual HTTP fetch and exact raw-response hash",
                        )
                    )
                if (
                    urlparse(snapshot_url).scheme != "https"
                    or (urlparse(snapshot_url).hostname or "").lower()
                    not in OFFICIAL_HOSTS
                    or urlparse(final_url).scheme != "https"
                    or (urlparse(final_url).hostname or "").lower()
                    not in OFFICIAL_HOSTS
                ):
                    report.errors.append(
                        issue(
                            "binding.web_snapshot_not_official_https",
                            f"private/web_source_snapshots.jsonl[{snapshot_ref}]",
                            "requested and final snapshot URLs must remain on the official HTTPS allowlist",
                        )
                    )
                fetch = fetches.get(snapshot_url)
                if fetch_rows and (
                    fetch is None
                    or fetch.get("raw_content_sha256") != raw_sha256
                    or fetch.get("support_excerpts") != excerpts
                    or fetch.get("support_text_normalization")
                    != SUPPORT_TEXT_NORMALIZATION
                    or fetch.get("metadata_sha256")
                    != snapshot.get("fetch_metadata_sha256")
                    or fetch.get("fetched_at") != snapshot.get("fetched_at")
                    or fetch.get("final_url") != final_url
                ):
                    report.errors.append(
                        issue(
                            "binding.web_fetch_manifest_mismatch",
                            f"private/web_source_snapshots.jsonl[{snapshot_ref}]",
                            "frozen snapshot differs from the actual-fetch manifest",
                        )
                    )
                if root is not None and isinstance(snapshot.get("raw_path"), str):
                    raw_path = (root / str(snapshot["raw_path"])).resolve()
                    if (
                        not raw_path.is_relative_to(root.resolve())
                        or not raw_path.is_file()
                    ):
                        report.errors.append(
                            issue(
                                "binding.web_raw_file_missing",
                                f"private/web_source_snapshots.jsonl[{snapshot_ref}].raw_path",
                                "raw official response is missing or outside the dataset root",
                            )
                        )
                    else:
                        raw = raw_path.read_bytes()
                        digest = hashlib.sha256(raw).hexdigest()
                        if digest != raw_sha256:
                            report.errors.append(
                                issue(
                                    "binding.web_raw_hash_mismatch",
                                    f"private/web_source_snapshots.jsonl[{snapshot_ref}].raw_path",
                                    "raw official response bytes do not match the frozen SHA-256",
                                )
                            )
                        visible = normalize_text(
                            response_text(
                                raw,
                                str(snapshot.get("text_encoding") or "utf-8"),
                                str(snapshot.get("content_type") or ""),
                            )
                        )
                        for fragment in excerpts:
                            if normalize_text(str(fragment)) not in visible:
                                report.errors.append(
                                    issue(
                                        "binding.web_excerpt_absent_from_normalized_dom",
                                        f"private/web_source_snapshots.jsonl[{snapshot_ref}].raw_path",
                                        "operative support excerpt is absent from normalized text extracted from the exact raw response",
                                    )
                                )
                if not isinstance(passport, Mapping):
                    continue
                if (
                    passport.get("snapshot_sha256") != raw_sha256
                    or passport.get("raw_content_sha256") != raw_sha256
                    or passport.get("snapshot_sha256_kind")
                    != "exact_http_response_bytes"
                    or passport.get("fetched_at")
                    != snapshot.get("fetched_at")
                    or passport.get("verified_as_of")
                    != snapshot.get("verified_as_of")
                    or passport.get("support_text_normalization")
                    != SUPPORT_TEXT_NORMALIZATION
                ):
                    report.errors.append(
                        issue(
                            "binding.web_passport_raw_snapshot_mismatch",
                            f"private/evidence_corpus.jsonl[{evidence_ids[0]}].source_passport",
                            "source passport does not bind to the exact raw official response",
                        )
                    )
                decision_time = gold.get("applicability", {}).get("decision_time")
                required_temporal_fields = (
                    "version",
                    "issued_at",
                    "issued_at_kind",
                    "effective_from",
                    "effective_from_basis",
                    "effective_interval_kind",
                )
                if any(
                    not isinstance(passport.get(field), str)
                    or not passport.get(field).strip()
                    for field in required_temporal_fields
                ):
                    report.errors.append(
                        issue(
                            "binding.web_temporal_passport_incomplete",
                            f"private/evidence_corpus.jsonl[{evidence_ids[0]}].source_passport",
                            "web passport lacks explicit source-version and effective-date semantics",
                        )
                    )
                snapshot_to_passport_fields = {
                    "source_version": "version",
                    "source_version_date": "issued_at",
                    "source_version_date_kind": "issued_at_kind",
                    "effective_from": "effective_from",
                    "effective_to": "effective_to",
                    "effective_from_basis": "effective_from_basis",
                    "effective_interval_kind": "effective_interval_kind",
                }
                if any(
                    snapshot.get(snapshot_field)
                    != passport.get(passport_field)
                    for snapshot_field, passport_field in (
                        snapshot_to_passport_fields.items()
                    )
                ):
                    report.errors.append(
                        issue(
                            "binding.web_temporal_snapshot_mismatch",
                            f"private/web_source_snapshots.jsonl[{snapshot_ref}]",
                            "snapshot temporal provenance differs from the selected evidence passport",
                        )
                    )
                try:
                    decision_date = date.fromisoformat(str(decision_time))
                    effective_from = date.fromisoformat(
                        str(passport.get("effective_from"))
                    )
                    effective_to = (
                        date.fromisoformat(str(passport.get("effective_to")))
                        if passport.get("effective_to") is not None
                        else None
                    )
                except ValueError:
                    report.errors.append(
                        issue(
                            "binding.web_temporal_date_invalid",
                            f"private/evidence_corpus.jsonl[{evidence_ids[0]}].source_passport",
                            "decision and effective dates must be ISO calendar dates",
                        )
                    )
                else:
                    if decision_date < effective_from or (
                        effective_to is not None and decision_date > effective_to
                    ):
                        report.errors.append(
                            issue(
                                "binding.web_not_effective_at_decision",
                                f"private/evidence_corpus.jsonl[{evidence_ids[0]}].source_passport",
                                "selected web source interval does not cover the decision date",
                            )
                        )
                    try:
                        verified_as_of = date.fromisoformat(
                            str(snapshot.get("verified_as_of"))
                        )
                    except ValueError:
                        report.errors.append(
                            issue(
                                "binding.web_verified_as_of_invalid",
                                f"private/web_source_snapshots.jsonl[{snapshot_ref}].verified_as_of",
                                "verified_as_of must be an ISO calendar date",
                            )
                        )
                    else:
                        if verified_as_of < decision_date:
                            report.errors.append(
                                issue(
                                    "binding.web_verified_before_decision",
                                    f"private/web_source_snapshots.jsonl[{snapshot_ref}].verified_as_of",
                                    "official response was verified before the represented decision date",
                                )
                            )
                if passport.get("issued_at") == decision_time and (
                    passport.get("issued_at_kind")
                    != "ecfr_point_in_time_edition_date"
                ):
                    report.errors.append(
                        issue(
                            "binding.web_decision_date_as_issue_date",
                            f"private/evidence_corpus.jsonl[{evidence_ids[0]}].source_passport.issued_at",
                            "decision date cannot masquerade as source issue date",
                        )
                    )
                if "ecfr.gov" in str(passport_url) and (
                    f"/api/versioner/v1/full/{decision_time}/"
                    not in str(passport_url)
                    or passport.get("issued_at_kind")
                    != "ecfr_point_in_time_edition_date"
                ):
                    report.errors.append(
                        issue(
                            "binding.web_ecfr_not_point_in_time",
                            f"private/evidence_corpus.jsonl[{evidence_ids[0]}].source_passport.url",
                            "eCFR evidence must use the decision-date point-in-time edition",
                        )
                    )
        else:
            report.errors.append(
                issue(
                    "binding.evidence_mode_invalid",
                    f"{path}.evidence_mode",
                    "evidence mode must be fresh-private or real-web",
                )
            )
    report.stats = {
        "tasks_checked": len(gold_rows),
        "fresh_private_checked": private_count,
        "real_web_checked": web_count,
    }
    return report


def audit_evidence_patch_binding(root: Path) -> BindingReport:
    root = root.resolve()
    public, public_errors = load_jsonl(
        root / "public" / "tasks_zh.jsonl", "public/tasks_zh.jsonl"
    )
    gold, gold_errors = load_jsonl(
        root / "private" / "gold.jsonl", "private/gold.jsonl"
    )
    evidence, evidence_errors = load_jsonl(
        root / "private" / "evidence_corpus.jsonl",
        "private/evidence_corpus.jsonl",
    )
    snapshots, snapshot_errors = load_jsonl(
        root / "private" / "web_source_snapshots.jsonl",
        "private/web_source_snapshots.jsonl",
    )
    fetches, fetch_errors = load_jsonl(
        root / "private" / "web_snapshots" / "fetch_manifest.jsonl",
        "private/web_snapshots/fetch_manifest.jsonl",
    )
    report = audit_binding_records(
        public,
        gold,
        evidence,
        snapshots,
        root=root,
        fetch_rows=fetches,
    )
    report.errors[:0] = [
        *public_errors,
        *gold_errors,
        *evidence_errors,
        *snapshot_errors,
        *fetch_errors,
    ]
    return report


def _format_human(report: BindingReport) -> str:
    lines = [
        f"SearchWorthyOR-100 evidence/patch binding gate: {'PASS' if report.ok else 'FAIL'}",
        f"errors={len(report.errors)} warnings={len(report.warnings)}",
    ]
    for entry in report.errors:
        lines.append(f"ERROR [{entry.code}] {entry.path}: {entry.message}")
    lines.append(f"stats={json.dumps(report.stats, ensure_ascii=False, sort_keys=True)}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = audit_evidence_patch_binding(args.root)
    print(
        json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        if args.json
        else _format_human(report)
    )
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
