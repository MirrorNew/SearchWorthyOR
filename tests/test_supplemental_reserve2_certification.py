import hashlib
import json
import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "staging"
OUTPUT = STAGING / "certified_sources" / "supplemental_reserve2"


def read_jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def normalized_sha256(text: str) -> str:
    normalized = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def test_reserve2_has_forty_dual_certified_replacements():
    audits = read_jsonl(STAGING / "supplemental_reserve2_audit.jsonl")
    replacements = read_jsonl(STAGING / "supplemental_reserve2_replacements.jsonl")
    assert len(audits) == 40
    assert len(replacements) == 40
    assert all(row["status"] == "unchanged_pass" for row in audits)
    assert all(row["solver_certificate_passed"] for row in audits)


def test_reserve2_is_disjoint_from_main_and_reserve1():
    main_ids = {
        row["source_id"] for row in read_jsonl(STAGING / "base_candidates.jsonl")
    }
    reserve1_ids = {
        row["source_id"]
        for row in read_jsonl(STAGING / "supplemental_reserve_audit.jsonl")
    }
    reserve2_ids = {
        row["source_id"]
        for row in read_jsonl(STAGING / "supplemental_reserve2_audit.jsonl")
    }
    assert len(reserve2_ids) == 40
    assert main_ids.isdisjoint(reserve2_ids)
    assert reserve1_ids.isdisjoint(reserve2_ids)


def test_reserve2_hashes_mapping_and_solver_checks():
    audits = read_jsonl(STAGING / "supplemental_reserve2_audit.jsonl")
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
        assert all(mapping["completeness_check"].values())
        assert certificate["gurobi"]["status"] == "OPTIMAL"
        assert certificate["copt"]["status"] == "OPTIMAL"
        assert certificate["checks"]["passed"] is True
        assert audit["legacy_answer_used_as_gold"] is False
        assert audit["legacy_code_used"] is False


def test_continuous_projection_remains_float():
    continuous_values = 0
    for certificate_path in OUTPUT.glob("*/solver_certificate.json"):
        directory = certificate_path.parent
        certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
        ir = json.loads((directory / "canonical_ir.json").read_text(encoding="utf-8"))
        vartypes = {variable["name"]: variable["vartype"] for variable in ir["variables"]}
        for solver_name in ("gurobi", "copt"):
            projection = certificate[solver_name]["projected_action"]
            for name, value in zip(ir["action_projection"], projection, strict=True):
                if vartypes[name] == "C":
                    continuous_values += 1
                    assert isinstance(value, float)
                else:
                    assert isinstance(value, int)
        assert certificate["action_projection_contract"][
            "continuous_preserved_as_float"
        ]
    assert continuous_values > 0


def test_reserve2_small_integer_oracle_coverage():
    certificates = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in OUTPUT.glob("*/solver_certificate.json")
    ]
    attempted = sum(
        certificate["independent_integer_enumeration"]["attempted"]
        for certificate in certificates
    )
    assert attempted >= 30

