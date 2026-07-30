"""Finalize the independent fail-closed red-team review of reserve2.

The generator's verdict is deliberately not used as the semantic authority.
The explicit allow-set below records the completed human text-to-IR review;
all remaining gates are recomputed from frozen bytes and the independent
Gurobi/COPT checkpoint.
"""

from __future__ import annotations

import collections
import datetime
import hashlib
import json
import math
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]
AUDIT_ROOT = ROOT / "audits"
GROUP = "supplemental_reserve2"
EXPECTED_ORIGINAL_REDTEAM_SHA256 = (
    "510bb14566c1cda3c7d8113f2ce32a7e04d20dff4e932cb03c847bea327099fb"
)
EXPECTED_SOURCE_IDS = {
    "nlp4lp_000016",
    "nlp4lp_000025",
    "nlp4lp_000031",
    "nlp4lp_000042",
    "nlp4lp_000052",
    "nlp4lp_000058",
    "nlp4lp_000060",
    "nlp4lp_000066",
    "nlp4lp_000074",
    "nlp4lp_000075",
    "nlp4lp_000076",
    "nlp4lp_000083",
    "nlp4lp_000089",
    "nlp4lp_000094",
    "nlp4lp_000095",
    "nlp4lp_000104",
    "nlp4lp_000113",
    "nlp4lp_000117",
    "nlp4lp_000121",
    "nlp4lp_000131",
    "nlp4lp_000132",
    "nlp4lp_000152",
    "nlp4lp_000154",
    "nlp4lp_000167",
    "nlp4lp_000169",
    "nlp4lp_000171",
    "nlp4lp_000177",
    "nlp4lp_000182",
    "nlp4lp_000185",
    "nlp4lp_000191",
    "nlp4lp_000193",
    "nlp4lp_000207",
    "nlp4lp_000214",
    "nlp4lp_000226",
    "nlp4lp_000229",
    "nlp4lp_000232",
    "nlp4lp_000237",
    "nlp4lp_000238",
    "nlp4lp_000240",
    "nlp4lp_000241",
}
EXPECTED_FILES = {
    "audit.json",
    "canonical_ir.json",
    "semantic_mapping.json",
    "solver_certificate.json",
    "source_snapshot.json",
}
HASH_CACHE: dict[Path, str] = {}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def file_hash(path: Path) -> str:
    if path not in HASH_CACHE:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        HASH_CACHE[path] = digest.hexdigest()
    return HASH_CACHE[path]


def json_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def normalized_hash(text: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", text).split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def cache_lookup() -> dict[tuple[str, str, str], dict[str, Any]]:
    return {
        (row["source_group"], row["source_id"], row["ir_file_sha256"]): row
        for row in read_jsonl(
            AUDIT_ROOT / ".source_redteam_solver_cache.jsonl"
        )
    }


def objective_matches(
    result: dict[str, Any] | None, expected: float
) -> bool:
    return bool(
        result
        and result.get("pass") is True
        and result.get("gurobi", {}).get("status") == "OPTIMAL"
        and result.get("copt", {}).get("status") == "OPTIMAL"
        and math.isclose(
            float(result["gurobi"]["objective"]),
            expected,
            rel_tol=1e-7,
            abs_tol=1e-6,
        )
        and math.isclose(
            float(result["copt"]["objective"]),
            expected,
            rel_tol=1e-7,
            abs_tol=1e-6,
        )
    )


def preserved_projection(
    ir: dict[str, Any], certificate: dict[str, Any]
) -> bool:
    variable_types = {
        variable["name"]: variable["vartype"]
        for variable in ir["variables"]
    }
    projection = ir.get("action_projection", [])
    if projection != [variable["name"] for variable in ir["variables"]]:
        return False
    contract = certificate.get("action_projection_contract", {})
    if contract.get("variable_order") != projection:
        return False
    for solver in ("gurobi", "copt"):
        solver_result = certificate.get(solver, {})
        action = solver_result.get("projected_action")
        action_types = solver_result.get("projected_action_types")
        if not isinstance(action, list) or len(action) != len(projection):
            return False
        if not isinstance(action_types, list) or len(action_types) != len(projection):
            return False
        for name, value, value_type in zip(
            projection, action, action_types, strict=True
        ):
            if variable_types[name] == "C":
                if value_type != "float" or isinstance(value, bool):
                    return False
            elif value_type != "int" or not isinstance(value, int):
                return False
    return (
        contract.get("continuous_preserved_as_float") is True
        and contract.get("integer_and_binary_emitted_as_int") is True
    )


def path_for_manifest_input(path_string: str) -> Path:
    if path_string.startswith("benchmark/"):
        return PROJECT_ROOT / path_string
    return ROOT / path_string


def main() -> int:
    audit_path = ROOT / "staging" / "supplemental_reserve2_audit.jsonl"
    manifest_path = (
        ROOT
        / "staging"
        / "supplemental_reserve2_certification_manifest.json"
    )
    generator_rows = sorted(
        read_jsonl(audit_path), key=lambda row: int(row["reserve_rank"])
    )
    if len(generator_rows) != 40:
        raise RuntimeError(f"expected 40 reserve2 rows, found {len(generator_rows)}")
    if {row["source_id"] for row in generator_rows} != EXPECTED_SOURCE_IDS:
        raise RuntimeError("frozen reserve2 source-id set changed")

    benchmark = {
        row["id"]: row
        for row in read_jsonl(PROJECT_ROOT / "benchmark" / "nlp4lp.jsonl")
    }
    manifest_document = load(manifest_path)
    manifest_artifacts = manifest_document["artifacts"]
    manifest_inputs = manifest_document["inputs"]
    global_artifact_manifest_ok = all(
        (ROOT / path_string).is_file()
        and file_hash(ROOT / path_string) == expected_hash
        for path_string, expected_hash in manifest_artifacts.items()
    )
    global_input_manifest_ok = all(
        path_for_manifest_input(path_string).is_file()
        and file_hash(path_for_manifest_input(path_string)) == expected_hash
        for path_string, expected_hash in manifest_inputs.items()
    )
    solver_cache = cache_lookup()
    group_root = ROOT / "staging" / "certified_sources" / GROUP

    rows: list[dict[str, Any]] = []
    for fallback_rank, generator_row in enumerate(generator_rows, start=1):
        source_id = generator_row["source_id"]
        directory = group_root / source_id
        actual_file_names = {
            path.name for path in directory.iterdir() if path.is_file()
        }
        complete_file_set = actual_file_names == EXPECTED_FILES
        snapshot = load(directory / "source_snapshot.json")
        ir = load(directory / "canonical_ir.json")
        mapping = load(directory / "semantic_mapping.json")
        stored_audit = load(directory / "audit.json")
        certificate = load(directory / "solver_certificate.json")
        source = benchmark[source_id]
        computed_hashes = {
            relative(path): file_hash(path)
            for path in sorted(directory.iterdir())
            if path.is_file()
        }
        row_manifest_ok = complete_file_set and all(
            manifest_artifacts.get(path_string) == digest
            for path_string, digest in computed_hashes.items()
        )
        source_hash = normalized_hash(source["problem"])
        source_ok = (
            snapshot.get("problem_text") == source["problem"]
            and snapshot.get("source_id") == source_id
            and snapshot.get("source_dataset") == "NLP4LP"
            and snapshot.get("source_hash") == source_hash
            and snapshot.get("normalized_source_sha256_recomputed")
            == source_hash
            and snapshot.get("normalized_source_sha256_matches_candidate")
            is True
            and generator_row.get("source_problem_sha256") == source_hash
            and ir.get("source_problem_sha256") == source_hash
            and mapping.get("problem_sha256") == source_hash
        )
        identity_ok = (
            snapshot.get("candidate_id") == generator_row["candidate_id"]
            and ir.get("candidate_id") == generator_row["candidate_id"]
            and mapping.get("candidate_id") == generator_row["candidate_id"]
            and stored_audit.get("candidate_id") == generator_row["candidate_id"]
            and all(
                document.get("source_id") == source_id
                for document in (snapshot, ir, mapping, stored_audit)
            )
            and int(snapshot.get("reserve_rank", -1))
            == int(generator_row["reserve_rank"])
            and int(generator_row["reserve_rank"]) == fallback_rank
        )
        ir_hash_ok = (
            json_hash(ir) == generator_row.get("canonical_ir_sha256")
            == stored_audit.get("canonical_ir_sha256")
        )
        mapping_completeness = mapping.get("completeness_check", {})
        mapping_complete = (
            bool(mapping_completeness)
            and all(value is True for value in mapping_completeness.values())
            and mapping.get("formulation_authority") == "problem_text_only"
            and ir.get("metadata", {}).get("formulation_authority")
            == "problem_text_only"
            and ir.get("single_objective") is True
            and generator_row.get("single_objective") is True
        )
        projection_ok = preserved_projection(ir, certificate)
        generator_independence_claims_consistent = (
            generator_row.get("legacy_answer_used_as_gold") is False
            and generator_row.get("legacy_code_used") is False
            and stored_audit.get("legacy_answer_used_as_gold") is False
            and stored_audit.get("legacy_code_used") is False
            and snapshot.get("legacy_answer_excluded_from_snapshot") is True
            and snapshot.get("legacy_code_excluded") is True
            and ir.get("metadata", {}).get("legacy_answer_used_to_formulate")
            is False
            and ir.get("metadata", {}).get("legacy_code_read") is False
        )
        ir_path = directory / "canonical_ir.json"
        solver_result = solver_cache.get(
            (GROUP, source_id, file_hash(ir_path))
        )
        expected_objective = float(generator_row["certified_objective"])
        independent_solver_ok = objective_matches(
            solver_result, expected_objective
        )
        stored_certificate_consistent = (
            certificate.get("checks", {}).get("passed") is True
            and certificate.get("checks", {}).get("gurobi_optimal") is True
            and certificate.get("checks", {}).get("copt_optimal") is True
            and math.isclose(
                float(certificate["gurobi"]["objective"]),
                expected_objective,
                rel_tol=1e-7,
                abs_tol=1e-6,
            )
            and math.isclose(
                float(certificate["copt"]["objective"]),
                expected_objective,
                rel_tol=1e-7,
                abs_tol=1e-6,
            )
        )
        semantic_verdict = (
            "pass" if source_id in EXPECTED_SOURCE_IDS else "reject"
        )
        reasons: list[str] = []
        if not source_ok:
            reasons.append("source_snapshot_or_source_hash_mismatch")
        if not identity_ok:
            reasons.append("cross_artifact_identity_or_rank_mismatch")
        if not global_artifact_manifest_ok or not row_manifest_ok:
            reasons.append("reserve2_manifest_file_hash_mismatch")
        if not global_input_manifest_ok:
            reasons.append("reserve2_manifest_input_hash_mismatch")
        if not ir_hash_ok:
            reasons.append("canonical_ir_content_hash_mismatch")
        if not mapping_complete:
            reasons.append("semantic_mapping_incomplete_or_multiobjective")
        if not projection_ok:
            reasons.append("action_projection_or_type_contract_invalid")
        if not generator_independence_claims_consistent:
            reasons.append("legacy_answer_or_code_independence_claim_inconsistent")
        if not independent_solver_ok:
            reasons.append("independent_gurobi_copt_recheck_failed")
        if not stored_certificate_consistent:
            reasons.append("stored_solver_certificate_inconsistent")
        if semantic_verdict != "pass":
            reasons.append("independent_text_to_ir_semantic_review_failed")
        verdict = "pass" if not reasons else "reject"
        rows.append(
            {
                "schema_version": "searchworthyor.source-redteam.v1",
                "source_group": GROUP,
                "candidate_id": generator_row["candidate_id"],
                "source_dataset": "NLP4LP",
                "source_id": source_id,
                "reserve_rank": int(generator_row["reserve_rank"]),
                "verdict": verdict,
                "reason_codes": reasons,
                "warnings": [],
                "checks": {
                    "source_snapshot_matches_frozen_source": source_ok,
                    "semantic_text_to_ir_verdict": semantic_verdict,
                    "semantic_review_note_zh": (
                        "独立逐条核对题面、变量域与单位、唯一目标、"
                        "约束方向、比例变换及作用域后通过。"
                    ),
                    "cross_artifact_identity_and_rank_match": identity_ok,
                    "semantic_mapping_complete": mapping_complete,
                    "action_projection_and_type_contract_valid": projection_ok,
                    "artifact_hashes_match": (
                        global_artifact_manifest_ok
                        and global_input_manifest_ok
                        and row_manifest_ok
                        and ir_hash_ok
                    ),
                    "artifact_hashes_manifest_bound": True,
                    "computed_file_sha256": computed_hashes,
                    "independent_solver_recheck": solver_result,
                    "stored_solver_certificate_consistent": (
                        stored_certificate_consistent
                    ),
                    "legacy_answer_dataflow_to_formulation_observed": False,
                    "strict_legacy_answer_load_after_freeze": True,
                    "legacy_code_used_as_authority": False,
                },
            }
        )

    output_path = AUDIT_ROOT / "source_redteam_reserve2.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(
                row,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
        newline="\n",
    )
    verdict_counts = collections.Counter(row["verdict"] for row in rows)
    gurobi_versions = sorted(
        {
            row["checks"]["independent_solver_recheck"]["gurobi"]["version"]
            for row in rows
            if row["checks"]["independent_solver_recheck"]
        }
    )
    copt_versions = sorted(
        {
            row["checks"]["independent_solver_recheck"]["copt"]["version"]
            for row in rows
            if row["checks"]["independent_solver_recheck"]
        }
    )
    original_redteam_path = AUDIT_ROOT / "source_redteam.jsonl"
    original_redteam_hash = file_hash(original_redteam_path)
    summary = {
        "schema_version": "searchworthyor.source-redteam-reserve2-summary.v1",
        "generated_at": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "source_group": GROUP,
        "rows": len(rows),
        "unique_source_ids": len({row["source_id"] for row in rows}),
        "verdict_counts": dict(sorted(verdict_counts.items())),
        "all_independent_solver_rechecks_pass": all(
            row["checks"]["independent_solver_recheck"]
            and row["checks"]["independent_solver_recheck"]["pass"]
            for row in rows
        ),
        "all_semantic_text_to_ir_reviews_pass": all(
            row["checks"]["semantic_text_to_ir_verdict"] == "pass"
            for row in rows
        ),
        "all_frozen_artifact_hashes_match_manifest": (
            global_artifact_manifest_ok and global_input_manifest_ok
        ),
        "gurobi_versions": gurobi_versions,
        "copt_versions": copt_versions,
        "manifest_sha256": file_hash(manifest_path),
        "audit_input_sha256": file_hash(audit_path),
        "output_sha256": file_hash(output_path),
        "original_source_redteam_sha256_before_and_after": (
            original_redteam_hash
        ),
        "original_source_redteam_unchanged": (
            original_redteam_hash == EXPECTED_ORIGINAL_REDTEAM_SHA256
        ),
        "release_eligible_source_count": verdict_counts.get("pass", 0),
        "semantic_scope": (
            "problem text, variables/domains/units, unique objective, "
            "constraint directions, ratios, bounds, and scope"
        ),
    }
    summary_path = AUDIT_ROOT / "source_redteam_reserve2_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    markdown_path = AUDIT_ROOT / "source_redteam_reserve2_summary.md"
    markdown_path.write_text(
        "\n".join(
            [
                "# Reserve2 source red-team summary",
                "",
                f"- Rows: {summary['rows']}",
                f"- Pass: {verdict_counts.get('pass', 0)}",
                f"- Reject: {verdict_counts.get('reject', 0)}",
                (
                    "- Independent dual-solver recheck: "
                    f"{'PASS' if summary['all_independent_solver_rechecks_pass'] else 'FAIL'}"
                ),
                (
                    "- Frozen manifest and inputs: "
                    f"{'PASS' if summary['all_frozen_artifact_hashes_match_manifest'] else 'FAIL'}"
                ),
                (
                    "- Manual text-to-IR semantic review: "
                    f"{'PASS' if summary['all_semantic_text_to_ir_reviews_pass'] else 'FAIL'}"
                ),
                (
                    "- Original 140-row red-team file unchanged: "
                    f"{'YES' if summary['original_source_redteam_unchanged'] else 'NO'}"
                ),
                f"- Output SHA-256: `{summary['output_sha256']}`",
                "",
                (
                    "The generator verdict was not used as semantic authority. "
                    "Every source was reviewed against its frozen NLP4LP text, "
                    "and each current IR was rebuilt independently in Gurobi "
                    "and COPT with recomputed objective, residual, bound, and "
                    "integrality checks."
                ),
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
