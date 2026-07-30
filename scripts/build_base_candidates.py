#!/usr/bin/env python3
"""Build the static SearchWorthyOR-100 base-candidate pool.

This stage performs source-level screening only. It deliberately does not solve
instances, certify objectives, promote legacy answers/code to gold, or make a
release decision.
"""

from __future__ import annotations

import ast
import collections
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable


DATASET_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BENCHMARK_ROOT = PROJECT_ROOT / "benchmark"
OUTPUT_PATH = DATASET_ROOT / "staging" / "base_candidates.jsonl"

SOURCE_PATHS = {
    "OptMinerBench": BENCHMARK_ROOT / "optminer_bench.jsonl",
    "NLP4LP": BENCHMARK_ROOT / "nlp4lp.jsonl",
    "MAMO-ComplexLP": BENCHMARK_ROOT / "mamo_complexlp.jsonl",
}

QUOTAS = {
    "OptMinerBench": 57,
    "NLP4LP": 33,
    "MAMO-ComplexLP": 10,
}

LINEAR_OMB_TYPES = {"LP", "MILP", "IP"}

# Locally documented problem/reference risks that are unsuitable for a base
# adjudication pool. OMB115 is also excluded because its historical result was
# solver/license-limited rather than a clean source-level adjudication case.
OMB_KNOWN_RISKS = {
    10: "problem_reference_conflict",
    53: "problem_reference_conflict",
    63: "problem_reference_conflict",
    85: "problem_reference_conflict",
    100: "problem_reference_conflict",
    101: "hidden_synthetic_instance",
    102: "hidden_or_synthetic_instance",
    103: "hidden_synthetic_instance",
    104: "problem_reference_conflict",
    105: "hidden_synthetic_instance",
    108: "hidden_synthetic_instance",
    109: "problem_reference_conflict",
    110: "problem_reference_conflict",
    111: "hidden_instance_and_multi_objective",
    113: "problem_reference_conflict",
    114: "hidden_synthetic_instance",
    115: "solver_license_limited_history",
    117: "problem_reference_conflict",
    120: "hidden_synthetic_instance",
    122: "problem_reference_conflict",
    124: "problem_reference_conflict",
    126: "problem_reference_conflict",
    128: "problem_reference_conflict",
}

MULTI_OBJECTIVE_LITERALS = (
    "multi-objective",
    "multiobjective",
    "multiple objectives",
    "lexicographic objective",
    "pareto",
    "secondary objective",
    "secondary objectives",
    "weighted sum",
    "combined weighted objective",
    "setobjectiven",
)

HIDDEN_INSTANCE_LITERALS = (
    "attached file",
    "separate file",
    "provided separately",
    "external file",
    "spreadsheet",
    "download the",
    "refer to the dataset",
    "given dataset",
    "not shown",
)

# OptMinerBench also ships legacy code, so source-level hidden-instance markers
# must be checked there even when the prose does not mention an external file.
OMB_HIDDEN_INSTANCE_LITERALS = HIDDEN_INSTANCE_LITERALS + (
    "np.random",
    "random.seed",
    "synthetic",
    "synthetic data",
    "create synthetic",
    "read_csv",
    "read_excel",
    "loadtxt",
    "genfromtxt",
    "files don't exist",
    "file doesn't exist",
)

MIN_OBJECTIVE_RE = re.compile(
    r"\b(?:minimi[sz](?:e|ing)|minimum|minimal|lowest|cheapest|shortest|smallest)\b"
    r"|\breduce\s+the\s+total\b"
    r"|\bleast\s+(?:total|cost|amount|expensive|possible)\b",
    re.IGNORECASE,
)
MAX_OBJECTIVE_RE = re.compile(
    r"\b(?:maximi[sz](?:e|ing)|maximum|maximal|highest|greatest)\b",
    re.IGNORECASE,
)

# Ten distinct formulation types were selected to avoid taking ten near-identical
# diet LPs from the source-ordered MAMO file.
MAMO_TYPE_STRATIFIED_IDS = (
    "mamo_complexlp_000001",  # LP
    "mamo_complexlp_000041",  # transportation
    "mamo_complexlp_000049",  # network_flow
    "mamo_complexlp_000060",  # TSP
    "mamo_complexlp_000140",  # facility_location
    "mamo_complexlp_000179",  # scheduling
    "mamo_complexlp_000186",  # shortest_path
    "mamo_complexlp_000198",  # portfolio
    "mamo_complexlp_000200",  # set_cover
    "mamo_complexlp_000207",  # inventory
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        row = json.loads(raw_line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} is not a JSON object")
        rows.append(row)
    return rows


def normalize_problem(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def source_hash(problem: str) -> str:
    return sha256_bytes(normalize_problem(problem).encode("utf-8"))


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def marker_hits(text: str, literals: Iterable[str]) -> list[str]:
    lowered = text.lower()
    return [literal for literal in literals if literal in lowered]


def omb_source_id(raw_id: Any) -> str:
    return f"OMB{int(raw_id):03d}"


def source_id_counts(
    rows: list[dict[str, Any]], dataset_name: str
) -> collections.Counter[str]:
    if dataset_name == "OptMinerBench":
        return collections.Counter(omb_source_id(row["id"]) for row in rows)
    return collections.Counter(str(row["id"]) for row in rows)


def problem_hash_groups(
    rows: list[dict[str, Any]], dataset_name: str
) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = collections.defaultdict(list)
    for row in rows:
        row_id = (
            omb_source_id(row["id"])
            if dataset_name == "OptMinerBench"
            else str(row["id"])
        )
        groups[source_hash(str(row.get("problem") or ""))].append(row_id)
    return dict(groups)


def parse_legacy_code(code: str) -> tuple[bool, str | None]:
    try:
        ast.parse(code)
    except SyntaxError as error:
        location = f"line {error.lineno}" if error.lineno else "unknown line"
        return False, f"{error.msg} ({location})"
    return True, None


def supplement_screen(row: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    problem = str(row.get("problem") or "").strip()
    normalized = normalize_problem(problem)
    hidden_hits = marker_hits(normalized, HIDDEN_INSTANCE_LITERALS)
    multi_hits = marker_hits(normalized, MULTI_OBJECTIVE_LITERALS)
    has_min = bool(MIN_OBJECTIVE_RE.search(normalized))
    has_max = bool(MAX_OBJECTIVE_RE.search(normalized))
    final_punctuation = bool(normalized) and normalized[-1] in ".?!)"

    reasons: list[str] = []
    if len(normalized) < 300:
        reasons.append("text_too_short")
    if not final_punctuation:
        reasons.append("missing_terminal_punctuation")
    if hidden_hits:
        reasons.append("external_or_hidden_data_marker")
    if multi_hits:
        reasons.append("explicit_multi_objective_marker")
    if has_min == has_max:
        reasons.append(
            "objective_direction_missing" if not has_min else "mixed_objective_directions"
        )

    details = {
        "text_length_chars": len(normalized),
        "terminal_punctuation": final_punctuation,
        "objective_direction": (
            "min"
            if has_min and not has_max
            else "max"
            if has_max and not has_min
            else "ambiguous"
        ),
        "multi_objective_marker_hits": multi_hits,
        "hidden_instance_marker_hits": hidden_hits,
        "screen_reasons": reasons,
    }
    return not reasons, details


def spread_select(rows: list[dict[str, Any]], quota: int) -> list[dict[str, Any]]:
    """Take deterministic source-order quantiles without random sampling."""

    if quota <= 0:
        return []
    if len(rows) < quota:
        raise ValueError(f"Only {len(rows)} eligible rows for quota {quota}")
    if quota == 1:
        return [rows[0]]
    indices = [round(index * (len(rows) - 1) / (quota - 1)) for index in range(quota)]
    if len(set(indices)) != quota:
        raise AssertionError("Quantile selection produced duplicate indices")
    return [rows[index] for index in indices]


def build_omb(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    id_counts = source_id_counts(rows, "OptMinerBench")
    hash_groups = problem_hash_groups(rows, "OptMinerBench")
    representative_by_hash = {
        digest: min(ids) for digest, ids in hash_groups.items()
    }

    syntax_errors: dict[int, str] = {}
    multi_objective_ids: set[int] = set()
    hidden_instance_marker_ids: set[int] = set()
    duplicate_nonrepresentatives: set[int] = set()
    nonlinear_type_ids: set[int] = set()
    eligible: list[dict[str, Any]] = []

    for row in sorted(rows, key=lambda item: int(item["id"])):
        raw_id = int(row["id"])
        row_source_id = omb_source_id(raw_id)
        problem = str(row.get("problem") or "")
        code = str(row.get("code") or "")
        digest = source_hash(problem)
        syntax_ok, syntax_error = parse_legacy_code(code)
        if not syntax_ok:
            syntax_errors[raw_id] = syntax_error or "SyntaxError"

        combined = f"{problem}\n{code}"
        multi_hits = marker_hits(combined, MULTI_OBJECTIVE_LITERALS)
        objective_call_count = len(
            re.findall(r"\.setobjective\s*\(", code, flags=re.IGNORECASE)
        )
        if objective_call_count > 1:
            multi_hits.append("multiple_setobjective_calls")
        if multi_hits:
            multi_objective_ids.add(raw_id)
        hidden_hits = marker_hits(combined, OMB_HIDDEN_INSTANCE_LITERALS)
        if hidden_hits:
            hidden_instance_marker_ids.add(raw_id)

        if representative_by_hash[digest] != row_source_id:
            duplicate_nonrepresentatives.add(raw_id)
        if str(row.get("type") or "").strip().upper() not in LINEAR_OMB_TYPES:
            nonlinear_type_ids.add(raw_id)

        excluded = (
            not syntax_ok
            or bool(multi_hits)
            or bool(hidden_hits)
            or raw_id in OMB_KNOWN_RISKS
            or raw_id in duplicate_nonrepresentatives
            or raw_id in nonlinear_type_ids
        )
        if excluded:
            continue

        duplicate_group = hash_groups[digest]
        eligible.append(
            {
                "_raw": row,
                "_source_id": row_source_id,
                "_source_hash": digest,
                "_screen": {
                    "text_length_chars": len(normalize_problem(problem)),
                    "terminal_punctuation": bool(normalize_problem(problem))
                    and normalize_problem(problem)[-1] in ".?!)",
                    "legacy_code_syntax_screen": "pass",
                    "multi_objective_marker_hits": [],
                    "hidden_instance_marker_hits": [],
                    "known_nonadjudicable_risk_screen": "pass",
                    "linear_model_type_screen": "pass",
                    "input_duplicate_resolution": (
                        f"representative_kept; removed={','.join(duplicate_group[1:])}"
                        if len(duplicate_group) > 1
                        else "not_applicable"
                    ),
                    "source_id_unique_in_input": id_counts[row_source_id] == 1,
                },
            }
        )

    selected = eligible[: QUOTAS["OptMinerBench"]]
    if len(selected) != QUOTAS["OptMinerBench"]:
        raise ValueError(
            f"OptMinerBench produced {len(selected)} rows, "
            f"expected {QUOTAS['OptMinerBench']}"
        )

    audit = {
        "input_count": len(rows),
        "eligible_count": len(eligible),
        "selected_count": len(selected),
        "syntax_error_ids": sorted(syntax_errors),
        "syntax_errors": syntax_errors,
        "multi_objective_ids": sorted(multi_objective_ids),
        "hidden_instance_marker_ids": sorted(hidden_instance_marker_ids),
        "known_risk_ids": sorted(OMB_KNOWN_RISKS),
        "nonlinear_type_ids": sorted(nonlinear_type_ids),
        "duplicate_nonrepresentative_ids": sorted(duplicate_nonrepresentatives),
        "eligible_not_selected_ids": [
            int(item["_raw"]["id"])
            for item in eligible[QUOTAS["OptMinerBench"] :]
        ],
    }
    return selected, audit


def build_nlp4lp(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    id_counts = source_id_counts(rows, "NLP4LP")
    hash_groups = problem_hash_groups(rows, "NLP4LP")
    eligible: list[dict[str, Any]] = []
    rejection_counts: collections.Counter[str] = collections.Counter()

    for row in rows:
        passed, screen = supplement_screen(row)
        digest = source_hash(str(row.get("problem") or ""))
        row_source_id = str(row["id"])
        if len(hash_groups[digest]) != 1:
            passed = False
            screen["screen_reasons"].append("duplicate_problem_hash_in_input")
        if id_counts[row_source_id] != 1:
            passed = False
            screen["screen_reasons"].append("duplicate_source_id_in_input")
        if not passed:
            rejection_counts.update(screen["screen_reasons"])
            continue
        eligible.append(
            {
                "_raw": row,
                "_source_id": row_source_id,
                "_source_hash": digest,
                "_screen": {
                    **screen,
                    "source_id_unique_in_input": True,
                    "source_hash_unique_in_input": True,
                },
            }
        )

    selected = spread_select(eligible, QUOTAS["NLP4LP"])
    audit = {
        "input_count": len(rows),
        "eligible_count": len(eligible),
        "selected_count": len(selected),
        "rejection_counts_with_overlap": dict(sorted(rejection_counts.items())),
    }
    return selected, audit


def build_mamo(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    id_counts = source_id_counts(rows, "MAMO-ComplexLP")
    hash_groups = problem_hash_groups(rows, "MAMO-ComplexLP")
    by_id = {str(row["id"]): row for row in rows}
    selected: list[dict[str, Any]] = []
    screened_eligible_count = 0
    rejection_counts: collections.Counter[str] = collections.Counter()

    for row in rows:
        passed, screen = supplement_screen(row)
        digest = source_hash(str(row.get("problem") or ""))
        row_source_id = str(row["id"])
        if len(hash_groups[digest]) != 1:
            passed = False
            screen["screen_reasons"].append("duplicate_problem_hash_in_input")
        if id_counts[row_source_id] != 1:
            passed = False
            screen["screen_reasons"].append("duplicate_source_id_in_input")
        if passed:
            screened_eligible_count += 1
        else:
            rejection_counts.update(screen["screen_reasons"])

    for row_source_id in MAMO_TYPE_STRATIFIED_IDS:
        if row_source_id not in by_id:
            raise KeyError(f"Missing curated MAMO source id: {row_source_id}")
        row = by_id[row_source_id]
        passed, screen = supplement_screen(row)
        digest = source_hash(str(row.get("problem") or ""))
        if len(hash_groups[digest]) != 1:
            passed = False
            screen["screen_reasons"].append("duplicate_problem_hash_in_input")
        if id_counts[row_source_id] != 1:
            passed = False
            screen["screen_reasons"].append("duplicate_source_id_in_input")
        if not passed:
            raise ValueError(
                f"Curated MAMO row {row_source_id} failed: "
                f"{screen['screen_reasons']}"
            )
        selected.append(
            {
                "_raw": row,
                "_source_id": row_source_id,
                "_source_hash": digest,
                "_screen": {
                    **screen,
                    "source_id_unique_in_input": True,
                    "source_hash_unique_in_input": True,
                },
            }
        )

    selected_types = [str(item["_raw"].get("type") or "") for item in selected]
    if len(selected) != QUOTAS["MAMO-ComplexLP"]:
        raise ValueError(
            f"MAMO-ComplexLP produced {len(selected)} rows, "
            f"expected {QUOTAS['MAMO-ComplexLP']}"
        )
    if len(set(selected_types)) != len(selected_types):
        raise ValueError("MAMO type-stratified selection contains duplicate types")

    audit = {
        "input_count": len(rows),
        "eligible_count": screened_eligible_count,
        "selected_count": len(selected),
        "selected_types": selected_types,
        "rejection_counts_with_overlap": dict(sorted(rejection_counts.items())),
    }
    return selected, audit


def public_candidate(
    ordinal: int, dataset_name: str, item: dict[str, Any]
) -> dict[str, Any]:
    row = item["_raw"]
    raw_scenario = str(row.get("scenario") or "").strip()
    raw_type = str(row.get("type") or "").strip()
    if dataset_name == "NLP4LP":
        scenario = raw_scenario or "Unspecified"
        problem_type = raw_type or "LP-family"
        metadata_origin = {
            "scenario": "source_blank",
            "type": "dataset_level_inference",
        }
    else:
        scenario = raw_scenario or "Unspecified"
        problem_type = raw_type or "Unspecified"
        metadata_origin = {
            "scenario": "source_field" if raw_scenario else "source_blank",
            "type": "source_field" if raw_type else "source_blank",
        }

    if dataset_name == "OptMinerBench":
        selection_reason = (
            "Source-order representative passed exact deduplication, legacy-code "
            "syntax parsing, explicit LP/MILP/IP type screening, single-objective "
            "marker screening, and the local known non-adjudicable-risk exclusion "
            "list."
        )
        legacy_code_status = "pending_manual_review_not_gold"
    elif dataset_name == "NLP4LP":
        selection_reason = (
            "Passed complete-text, single-objective-direction, no-hidden-data, "
            "and exact-dedup screens; selected by deterministic source-order "
            "quantile coverage."
        )
        legacy_code_status = "not_provided"
    else:
        selection_reason = (
            "Passed complete-text, single-objective-direction, no-hidden-data, "
            "and exact-dedup screens; selected in a curated ten-type formulation "
            "stratum."
        )
        legacy_code_status = "not_provided"

    static_audit = {
        **item["_screen"],
        "selected_candidate_id_unique": True,
        "selected_source_id_unique": True,
        "selected_source_hash_unique": True,
        "single_objective_screen": "pass",
        "hidden_instance_screen": "pass",
        "legacy_answer_status": "pending_manual_review_not_gold",
        "legacy_code_status": legacy_code_status,
        "metadata_origin": metadata_origin,
    }
    static_audit.pop("screen_reasons", None)

    return {
        "candidate_id": f"SWOR-BASE-{ordinal:03d}",
        "source_dataset": dataset_name,
        "source_id": item["_source_id"],
        "source_hash": item["_source_hash"],
        "problem_zh_or_en": str(row["problem"]).strip(),
        "scenario": scenario,
        "type": problem_type,
        "static_audit": static_audit,
        "status": "selected_for_manual_review",
        "selection_reason": selection_reason,
    }


def write_outputs(
    candidates: list[dict[str, Any]],
    source_rows: dict[str, list[dict[str, Any]]],
    audits: dict[str, dict[str, Any]],
) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = "".join(
        json.dumps(candidate, ensure_ascii=False, separators=(",", ":")) + "\n"
        for candidate in candidates
    )
    OUTPUT_PATH.write_text(payload, encoding="utf-8", newline="\n")

    dataset_counts = collections.Counter(
        candidate["source_dataset"] for candidate in candidates
    )
    candidate_ids = [candidate["candidate_id"] for candidate in candidates]
    source_keys = [
        (candidate["source_dataset"], candidate["source_id"])
        for candidate in candidates
    ]
    source_hashes = [candidate["source_hash"] for candidate in candidates]
    required_keys = {
        "candidate_id",
        "source_dataset",
        "source_id",
        "source_hash",
        "problem_zh_or_en",
        "scenario",
        "type",
        "static_audit",
        "status",
        "selection_reason",
    }

    assert len(candidates) == 100
    assert dataset_counts == collections.Counter(QUOTAS)
    assert len(set(candidate_ids)) == 100
    assert len(set(source_keys)) == 100
    assert len(set(source_hashes)) == 100
    assert all(set(candidate) == required_keys for candidate in candidates)
    assert all(
        re.fullmatch(r"[0-9a-f]{64}", candidate["source_hash"])
        for candidate in candidates
    )
    assert all(
        candidate["status"] == "selected_for_manual_review"
        for candidate in candidates
    )
    assert len(source_rows["OptMinerBench"]) == 128
    assert len(source_rows["NLP4LP"]) == 242
    assert len(source_rows["MAMO-ComplexLP"]) == 211
    assert audits["OptMinerBench"]["selected_count"] == 57
    assert audits["NLP4LP"]["selected_count"] == 33
    assert audits["MAMO-ComplexLP"]["selected_count"] == 10


def main() -> None:
    source_rows = {
        name: read_jsonl(path) for name, path in SOURCE_PATHS.items()
    }
    omb_selected, omb_audit = build_omb(source_rows["OptMinerBench"])
    nlp_selected, nlp_audit = build_nlp4lp(source_rows["NLP4LP"])
    mamo_selected, mamo_audit = build_mamo(source_rows["MAMO-ComplexLP"])

    ordered_groups = (
        ("OptMinerBench", omb_selected),
        ("NLP4LP", nlp_selected),
        ("MAMO-ComplexLP", mamo_selected),
    )
    candidates: list[dict[str, Any]] = []
    for dataset_name, items in ordered_groups:
        for item in items:
            candidates.append(
                public_candidate(len(candidates) + 1, dataset_name, item)
            )

    write_outputs(
        candidates,
        source_rows,
        {
            "OptMinerBench": omb_audit,
            "NLP4LP": nlp_audit,
            "MAMO-ComplexLP": mamo_audit,
        },
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT_PATH),
                "counts": collections.Counter(
                    candidate["source_dataset"] for candidate in candidates
                ),
                "output_sha256": file_sha256(OUTPUT_PATH),
                "builder_sha256": file_sha256(Path(__file__).resolve()),
                "source_sha256": {
                    name: file_sha256(path) for name, path in SOURCE_PATHS.items()
                },
            },
            ensure_ascii=False,
            default=dict,
        )
    )


if __name__ == "__main__":
    main()
