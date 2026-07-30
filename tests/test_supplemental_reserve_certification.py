import hashlib
import json
import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "staging"
OUTPUT = STAGING / "certified_sources" / "supplemental_reserve"


def read_jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def normalized_sha256(text: str) -> str:
    normalized = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def test_reserve_has_at_least_forty_dual_certified_rows():
    audits = read_jsonl(STAGING / "supplemental_reserve_audit.jsonl")
    replacements = read_jsonl(STAGING / "supplemental_reserve_replacements.jsonl")
    assert len(audits) >= 40
    assert len(replacements) >= 40
    assert all(row["status"] == "unchanged_pass" for row in audits)
    assert all(row["solver_certificate_passed"] for row in audits)
    assert [row["replacement_rank"] for row in replacements] == list(
        range(1, len(replacements) + 1)
    )


def test_reserve_is_disjoint_from_selected_sources():
    selected = {
        row["source_id"]
        for row in read_jsonl(STAGING / "base_candidates.jsonl")
    }
    reserves = {
        row["source_id"]
        for row in read_jsonl(STAGING / "supplemental_reserve_audit.jsonl")
    }
    assert selected.isdisjoint(reserves)
    assert len(reserves) == 40


def test_reserve_artifacts_and_hashes():
    audits = read_jsonl(STAGING / "supplemental_reserve_audit.jsonl")
    for audit in audits:
        directory = OUTPUT / audit["source_id"]
        source = json.loads(
            (directory / "source_snapshot.json").read_text(encoding="utf-8")
        )
        mapping = json.loads(
            (directory / "semantic_mapping.json").read_text(encoding="utf-8")
        )
        certificate = json.loads(
            (directory / "solver_certificate.json").read_text(encoding="utf-8")
        )
        assert normalized_sha256(source["problem_text"]) == audit["source_problem_sha256"]
        assert source["legacy_answer_excluded_from_snapshot"] is True
        assert source["legacy_code_excluded"] is True
        assert all(mapping["completeness_check"].values())
        assert certificate["gurobi"]["status"] == "OPTIMAL"
        assert certificate["copt"]["status"] == "OPTIMAL"
        assert certificate["checks"]["passed"] is True
        assert audit["legacy_answer_used_as_gold"] is False
        assert audit["legacy_code_used"] is False


def test_small_integer_reserves_use_enumeration_when_tractable():
    certificates = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in OUTPUT.glob("*/solver_certificate.json")
    ]
    attempted = sum(
        certificate["independent_integer_enumeration"]["attempted"]
        for certificate in certificates
    )
    assert attempted >= 30

