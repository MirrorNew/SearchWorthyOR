import hashlib
import json
import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "staging"
OUTPUT = STAGING / "certified_sources" / "supplemental"


def read_jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def normalized_sha256(text: str) -> str:
    normalized = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def test_exact_supplemental_audit_coverage():
    selected = [
        row
        for row in read_jsonl(STAGING / "base_candidates.jsonl")
        if row["source_dataset"] in {"NLP4LP", "MAMO-ComplexLP"}
    ]
    audits = read_jsonl(STAGING / "supplemental_base_audit.jsonl")
    assert len(selected) == 43
    assert len(audits) == 43
    assert {row["source_id"] for row in selected} == {
        row["source_id"] for row in audits
    }
    assert sum(row["status"] == "unchanged_pass" for row in audits) == 38
    assert sum(row["status"] == "rejected" for row in audits) == 5


def test_source_hashes_and_provenance_boundary():
    candidates = {
        row["candidate_id"]: row
        for row in read_jsonl(STAGING / "base_candidates.jsonl")
        if row["source_dataset"] in {"NLP4LP", "MAMO-ComplexLP"}
    }
    for candidate_id, candidate in candidates.items():
        snapshot = json.loads(
            (OUTPUT / candidate_id / "source_snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        assert normalized_sha256(snapshot["problem_text"]) == candidate["source_hash"]
        assert snapshot["legacy_answer_excluded_from_snapshot"] is True
        assert snapshot["legacy_code_excluded"] is True


def test_pass_rows_have_complete_mapping_and_dual_solver_certificate():
    audits = read_jsonl(STAGING / "supplemental_base_audit.jsonl")
    for audit in audits:
        if audit["status"] != "unchanged_pass":
            continue
        candidate_dir = OUTPUT / audit["candidate_id"]
        ir = json.loads((candidate_dir / "canonical_ir.json").read_text(encoding="utf-8"))
        mapping = json.loads(
            (candidate_dir / "semantic_mapping.json").read_text(encoding="utf-8")
        )
        certificate = json.loads(
            (candidate_dir / "solver_certificate.json").read_text(encoding="utf-8")
        )
        assert ir["single_objective"] is True
        assert all(mapping["completeness_check"].values())
        assert certificate["gurobi"]["status"] == "OPTIMAL"
        assert certificate["copt"]["status"] == "OPTIMAL"
        assert certificate["checks"]["passed"] is True
        assert certificate["solver_only_proxy_bounds"]["not_part_of_canonical_ir"]
        assert audit["legacy_code_used"] is False
        assert audit["legacy_answer_used_as_gold"] is False


def test_rejected_rows_do_not_claim_a_certified_model():
    audits = read_jsonl(STAGING / "supplemental_base_audit.jsonl")
    for audit in audits:
        if audit["status"] != "rejected":
            continue
        candidate_dir = OUTPUT / audit["candidate_id"]
        rejection = json.loads(
            (candidate_dir / "rejection.json").read_text(encoding="utf-8")
        )
        assert rejection["model_generated"] is False
        assert rejection["legacy_answer_used_as_gold"] is False
        assert not (candidate_dir / "canonical_ir.json").exists()

