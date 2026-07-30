import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "assemble_certified_pool.py"
SPEC = importlib.util.spec_from_file_location("assemble_certified_pool", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
ASSEMBLER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ASSEMBLER
SPEC.loader.exec_module(ASSEMBLER)

FAMILY_TEST_PHRASES = {
    "routing_transport": "A vehicle routing delivery problem",
    "scheduling_workforce": "A workforce shift scheduling problem",
    "production_capacity": "A manufacturing production problem",
    "assignment_matching": "A one-to-one assignment matching problem",
    "facility_network": "A facility location opening problem",
    "inventory_supply_chain": "An inventory replenishment supply chain problem",
    "energy_environment": "An electricity energy emission problem",
    "healthcare_resources": "A hospital patient healthcare problem",
    "finance_portfolio": "A financial investment portfolio problem",
    "telecom_service": "A telecom bandwidth server problem",
}


def compact_hash(value):
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_hash(text):
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(
                row, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def make_artifacts(root, group, candidate_id, dataset, source_id, problem):
    problem_sha = normalized_hash(problem)
    if group == "optminer":
        directory = root / "staging" / "certified_sources" / group / candidate_id
    elif group == "supplemental_base":
        directory = (
            root / "staging" / "certified_sources" / "supplemental" / candidate_id
        )
    elif group == "supplemental_reserve":
        directory = (
            root
            / "staging"
            / "certified_sources"
            / "supplemental_reserve"
            / source_id
        )
    else:
        directory = (
            root
            / "staging"
            / "certified_sources"
            / "supplemental_reserve2"
            / source_id
        )
    snapshot = {
        "candidate_id": candidate_id,
        "source_dataset": dataset,
        "source_id": source_id,
        "problem_text": problem,
        "normalized_source_sha256_recomputed": problem_sha,
        "source_hash": problem_sha,
        "legacy_answer_excluded_from_snapshot": True,
        "legacy_code_excluded": True,
    }
    ir = {
        "schema_version": "1.0",
        "candidate_id": candidate_id,
        "source_dataset": dataset,
        "source_id": source_id,
        "source_problem_sha256": problem_sha,
        "single_objective": True,
        "sense": "min",
        "variables": [
            {
                "name": "x",
                "lb": 0,
                "ub": 10,
                "vartype": "I",
            }
        ],
        "constraints": [
            {
                "name": "floor",
                "sense": ">=",
                "rhs": 1,
                "terms": {"x": 1},
            }
        ],
        "objective": {
            "name": "minimum",
            "constant": 0,
            "terms": {"x": 1},
        },
        "action_projection": ["x"],
    }
    mapping = {
        "candidate_id": candidate_id,
        "source_id": source_id,
        "problem_sha256": problem_sha,
        "formulation_authority": "problem_text_only",
        "semantic_risks": [],
        "completeness_check": {
            "sets_mapped": True,
            "parameters_mapped": True,
            "variables_mapped": True,
            "single_objective_mapped": True,
            "constraints_mapped": True,
            "units_mapped": True,
        },
        "sets": {"items": ["one"]},
        "parameters": {"floor": 1},
        "variables": [{"name": "x", "source_claim": problem}],
        "constraints": [{"name": "floor", "source_claim": problem}],
        "objective": {
            "direction": "min",
            "name": "minimum",
            "terms": {"x": 1},
            "source_claim": problem,
        },
    }
    solver_result = {
        "status": "OPTIMAL",
        "objective": 1,
        "objective_recomputed": 1,
        "assignment": {"x": 1},
        "projected_action": [1],
        "max_constraint_violation": 0,
        "bound_violation": 0,
        "integrality_violation": 0,
    }
    certificate = {
        "checks": {"passed": True},
        "gurobi": {**solver_result, "solver": "gurobi"},
        "copt": {**solver_result, "solver": "copt"},
    }
    if group == "optminer":
        ir["canonical_sha256"] = compact_hash(
            {key: value for key, value in ir.items() if key != "canonical_sha256"}
        )
    paths = {
        "source_snapshot": directory / "source_snapshot.json",
        "semantic_mapping": directory / "semantic_mapping.json",
        "canonical_ir": directory / "canonical_ir.json",
        "solver_certificate": directory / "solver_certificate.json",
    }
    for name, value in (
        ("source_snapshot", snapshot),
        ("semantic_mapping", mapping),
        ("canonical_ir", ir),
        ("solver_certificate", certificate),
    ):
        write_json(paths[name], value)
    return {
        "problem_sha": problem_sha,
        "snapshot": snapshot,
        "mapping": mapping,
        "ir": ir,
        "certificate": certificate,
        "paths": paths,
        "hashes": {
            path.relative_to(root).as_posix(): file_hash(path)
            for path in paths.values()
        },
    }


def review_b_checks():
    return {name: True for name in ASSEMBLER.REVIEW_B_REQUIRED_CHECKS}


def build_fixture(root):
    optminer_audits = []
    supplemental_audits = []
    reserve_audits = []
    reserve2_audits = []
    base_candidates = []
    redteam = []
    review_b = []
    redteam_reserve2 = []
    review_b_reserve2 = []
    supplemental_manifest_hashes = {}
    reserve_manifest_hashes = {}
    reserve2_manifest_hashes = {}

    specifications = []
    for index in range(1, 31):
        specifications.append(
            (
                "optminer",
                f"SWOR-BASE-{index:03d}",
                "OptMinerBench",
                f"OMB{index:03d}",
                None,
            )
        )
    for index in range(38):
        specifications.append(
            (
                "supplemental_base",
                f"SWOR-BASE-{58 + index:03d}",
                "NLP4LP",
                f"nlp4lp_{index + 1:06d}",
                None,
            )
        )
    for rank in range(1, 41):
        specifications.append(
            (
                "supplemental_reserve",
                f"RESERVE-NLP4LP-{1000 + rank:06d}",
                "NLP4LP",
                f"nlp4lp_{1000 + rank:06d}",
                rank,
            )
        )
    for rank in range(1, 41):
        specifications.append(
            (
                "supplemental_reserve2",
                f"RESERVE2-NLP4LP-{2000 + rank:06d}",
                "NLP4LP",
                f"nlp4lp_{2000 + rank:06d}",
                rank,
            )
        )

    for serial, (group, candidate_id, dataset, source_id, rank) in enumerate(
        specifications, start=1
    ):
        family = ASSEMBLER.FAMILIES[(serial - 1) % len(ASSEMBLER.FAMILIES)]
        problem = (
            f"{FAMILY_TEST_PHRASES[family]}. "
            f"Problem {serial}: choose integer x at least one."
        )
        artifacts = make_artifacts(
            root, group, candidate_id, dataset, source_id, problem
        )
        paths = artifacts["paths"]
        hashes = artifacts["hashes"]
        if group == "optminer":
            base_candidates.append(
                {
                    "candidate_id": candidate_id,
                    "source_dataset": dataset,
                    "source_id": source_id,
                    "source_hash": artifacts["problem_sha"],
                    "problem_zh_or_en": problem,
                    "scenario": "Synthetic",
                    "type": "IP",
                    "static_audit": {},
                    "status": "selected_for_manual_review",
                    "selection_reason": "test",
                }
            )
            optminer_audits.append(
                {
                    "source_id": source_id,
                    "status": "certified",
                    "legacy_answer_policy": "not_read_not_gold",
                    "problem_sha256": hashlib.sha256(problem.encode("utf-8")).hexdigest(),
                    "ir_path": paths["canonical_ir"].relative_to(root).as_posix(),
                    "ir_sha256": file_hash(paths["canonical_ir"]),
                    "canonical_ir_sha256": artifacts["ir"]["canonical_sha256"],
                    "certificate_path": paths["solver_certificate"]
                    .relative_to(root)
                    .as_posix(),
                    "certificate_sha256": file_hash(paths["solver_certificate"]),
                    "source_snapshot_path": paths["source_snapshot"]
                    .relative_to(root)
                    .as_posix(),
                    "semantic_mapping_path": paths["semantic_mapping"]
                    .relative_to(root)
                    .as_posix(),
                    "solver_checks": {"passed": True},
                    "ast_safety_screen": {"passed": True},
                }
            )
        else:
            prefix = root / "staging"
            files = {
                name: path.relative_to(prefix).as_posix()
                for name, path in paths.items()
            }
            audit = {
                "candidate_id": candidate_id,
                "source_dataset": dataset,
                "source_id": source_id,
                "source_problem_sha256": artifacts["problem_sha"],
                "canonical_ir_sha256": compact_hash(artifacts["ir"]),
                "status": "unchanged_pass",
                "solver_certificate_passed": True,
                "semantic_mapping_complete": True,
                "single_objective": True,
                "legacy_answer_used_as_gold": False,
                "legacy_code_used": False,
                "files": files,
            }
            if group == "supplemental_base":
                supplemental_audits.append(audit)
                supplemental_manifest_hashes.update(hashes)
            elif group == "supplemental_reserve":
                audit["reserve_rank"] = rank
                reserve_audits.append(audit)
                reserve_manifest_hashes.update(hashes)
            else:
                audit["reserve_rank"] = rank
                audit.pop("files")
                reserve2_audits.append(audit)
                reserve2_manifest_hashes.update(hashes)

        redteam_group = "supplemental" if group == "supplemental_base" else group
        redteam_row = {
            "schema_version": "1.0",
            "source_group": redteam_group,
            "candidate_id": candidate_id,
            "source_dataset": dataset,
            "source_id": source_id,
            "verdict": "pass",
            "reason_codes": [],
            "warnings": [],
            "checks": {
                "source_snapshot_matches_frozen_source": True,
                "semantic_text_to_ir_verdict": "pass",
                "artifact_hashes_match": True,
                "computed_file_sha256": hashes,
                "independent_solver_recheck": {
                    "gurobi": {"status": "OPTIMAL"},
                    "copt": {"status": "OPTIMAL"},
                    "pass": True,
                },
                "legacy_answer_dataflow_to_formulation_observed": False,
            },
        }
        if group == "optminer":
            redteam_row["structural_gate_verdict"] = "pass"
            redteam_row["current_audit_status"] = "certified"
        if group == "supplemental_reserve2":
            redteam_row["reserve_rank"] = rank
            redteam_reserve2.append(redteam_row)
        else:
            redteam.append(redteam_row)
        review_b_row = {
            "source_group": group,
            "source_list": (
                "base"
                if group == "supplemental_base"
                else "reserve"
                if group == "supplemental_reserve"
                else "reserve2"
                if group == "supplemental_reserve2"
                else "optminer"
            ),
            "candidate_id": candidate_id,
            "source_dataset": dataset,
            "source_id": source_id,
            "decision": "pass",
            "reasons": [],
            "checks": review_b_checks(),
        }
        if group == "supplemental_reserve2":
            review_b_row["reserve_rank"] = rank
            review_b_reserve2.append(review_b_row)
        else:
            review_b.append(review_b_row)

    write_jsonl(root / ASSEMBLER.OPTMINER_AUDIT, optminer_audits)
    write_jsonl(root / ASSEMBLER.SUPPLEMENTAL_AUDIT, supplemental_audits)
    write_jsonl(root / ASSEMBLER.RESERVE_AUDIT, reserve_audits)
    write_jsonl(root / ASSEMBLER.RESERVE2_AUDIT, reserve2_audits)
    write_jsonl(root / ASSEMBLER.BASE_CANDIDATES, base_candidates)
    write_json(
        root / ASSEMBLER.SUPPLEMENTAL_MANIFEST,
        {"schema_version": "1.0", "artifacts": supplemental_manifest_hashes},
    )
    write_json(
        root / ASSEMBLER.RESERVE_MANIFEST,
        {"schema_version": "1.0", "artifacts": reserve_manifest_hashes},
    )
    write_json(
        root / ASSEMBLER.RESERVE2_MANIFEST,
        {"schema_version": "1.0", "artifacts": reserve2_manifest_hashes},
    )
    write_jsonl(root / ASSEMBLER.REDTEAM_REVIEW, redteam)
    write_jsonl(root / ASSEMBLER.REDTEAM_REVIEW_RESERVE2, redteam_reserve2)
    write_jsonl(root / ASSEMBLER.REVIEW_B, review_b)
    write_jsonl(root / ASSEMBLER.REVIEW_B_RESERVE2, review_b_reserve2)


def assert_no_outputs(root):
    assert not (root / ASSEMBLER.POOL_OUTPUT).exists()
    assert not (root / ASSEMBLER.SUMMARY_OUTPUT).exists()
    assert not (root / ASSEMBLER.POOL_MANIFEST_OUTPUT).exists()


def assert_no_inspiration_outputs(root):
    assert not (root / ASSEMBLER.INSPIRATION_OUTPUT).exists()
    assert not (root / ASSEMBLER.INSPIRATION_SUMMARY_OUTPUT).exists()
    assert not (root / ASSEMBLER.INSPIRATION_MANIFEST_OUTPUT).exists()


def test_exact_priority_mix_and_manifest_hashes(tmp_path):
    build_fixture(tmp_path)
    assert ASSEMBLER.main(["--root", str(tmp_path)]) == 0
    records = read_jsonl(tmp_path / ASSEMBLER.POOL_OUTPUT)
    summary = json.loads(
        (tmp_path / ASSEMBLER.SUMMARY_OUTPUT).read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (tmp_path / ASSEMBLER.POOL_MANIFEST_OUTPUT).read_text(encoding="utf-8")
    )
    assert len(records) == 100
    assert summary["source_mix"]["by_source_group"] == {
        "optminer": 30,
        "supplemental_base": 38,
        "supplemental_reserve": 32,
    }
    assert summary["selected_reserve_ranks"] == list(range(1, 33))
    assert summary["selected_reserve2_ranks"] == []
    assert summary["family_counts"] == {
        family: 10 for family in ASSEMBLER.FAMILIES
    }
    assert all(row["source_status"]["dual_blind_review_passed"] for row in records)
    assert all(row["original_problem_text"] for row in records)
    assert all(row["semantic_mapping"] for row in records)
    assert all(row["family_assignment"]["score"] > 0 for row in records)
    assert all(row["family_assignment"]["matched_evidence"] for row in records)
    pool_entry = manifest["outputs"][ASSEMBLER.POOL_OUTPUT.as_posix()]
    assert pool_entry["sha256"] == file_hash(tmp_path / ASSEMBLER.POOL_OUTPUT)
    assert pool_entry["records"] == 100


def test_review_disagreement_and_hash_drift_use_later_reserves(tmp_path):
    build_fixture(tmp_path)
    redteam_path = tmp_path / ASSEMBLER.REDTEAM_REVIEW
    redteam = read_jsonl(redteam_path)
    redteam[0]["verdict"] = "reject"
    redteam[0]["reason_codes"] = ["semantic_gap"]
    write_jsonl(redteam_path, redteam)
    review_b_path = tmp_path / ASSEMBLER.REVIEW_B
    review_b = read_jsonl(review_b_path)
    review_b[31]["decision"] = "reject"
    review_b[31]["reasons"] = ["projection_gap"]
    write_jsonl(review_b_path, review_b)
    broken = (
        tmp_path
        / "staging"
        / "certified_sources"
        / "supplemental"
        / "SWOR-BASE-060"
        / "solver_certificate.json"
    )
    certificate = json.loads(broken.read_text(encoding="utf-8"))
    certificate["checks"]["passed"] = False
    write_json(broken, certificate)

    assert ASSEMBLER.main(["--root", str(tmp_path)]) == 0
    summary = json.loads(
        (tmp_path / ASSEMBLER.SUMMARY_OUTPUT).read_text(encoding="utf-8")
    )
    assert summary["source_mix"]["by_source_group"] == {
        "optminer": 29,
        "supplemental_base": 36,
        "supplemental_reserve": 35,
    }
    assert summary["selected_reserve_ranks"] == list(range(1, 36))
    assert summary["selected_reserve2_ranks"] == []
    assert summary["disqualified_count"] == 3


def test_fewer_than_100_exits_one_without_partial_outputs(tmp_path):
    build_fixture(tmp_path)
    redteam_path = tmp_path / ASSEMBLER.REDTEAM_REVIEW
    redteam = read_jsonl(redteam_path)
    for row in redteam[:49]:
        row["verdict"] = "reject"
        row["reason_codes"] = ["blind_reject"]
    write_jsonl(redteam_path, redteam)
    assert ASSEMBLER.main(["--root", str(tmp_path)]) == 1
    assert_no_outputs(tmp_path)


def test_reserve2_follows_reserve1_and_preserves_family_balance(tmp_path):
    build_fixture(tmp_path)
    redteam_path = tmp_path / ASSEMBLER.REDTEAM_REVIEW
    redteam = read_jsonl(redteam_path)
    for row in redteam[:10]:
        row["verdict"] = "reject"
        row["reason_codes"] = ["blind_reject"]
    write_jsonl(redteam_path, redteam)
    assert ASSEMBLER.main(["--root", str(tmp_path)]) == 0
    summary = json.loads(
        (tmp_path / ASSEMBLER.SUMMARY_OUTPUT).read_text(encoding="utf-8")
    )
    assert summary["source_mix"]["by_source_group"] == {
        "optminer": 20,
        "supplemental_base": 38,
        "supplemental_reserve": 40,
        "supplemental_reserve2": 2,
    }
    assert summary["selected_reserve_ranks"] == list(range(1, 41))
    assert summary["selected_reserve2_ranks"] == [1, 2]
    assert summary["family_counts"] == {
        family: 10 for family in ASSEMBLER.FAMILIES
    }


def test_inspiration_only_is_separately_named_and_has_no_family_claim(tmp_path):
    build_fixture(tmp_path)
    assert (
        ASSEMBLER.main(
            ["--root", str(tmp_path), "--inspiration-only"]
        )
        == 0
    )
    records = read_jsonl(tmp_path / ASSEMBLER.INSPIRATION_OUTPUT)
    summary = json.loads(
        (tmp_path / ASSEMBLER.INSPIRATION_SUMMARY_OUTPUT).read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (tmp_path / ASSEMBLER.INSPIRATION_MANIFEST_OUTPUT).read_text(
            encoding="utf-8"
        )
    )
    assert len(records) == 100
    assert all(
        row["role"] == "reviewed_background_inspiration_only"
        for row in records
    )
    assert all(row["source_correspondence_claim"] is False for row in records)
    assert all(row["family"] is None for row in records)
    assert all(row["family_assignment"] is None for row in records)
    assert summary["mode"] == "inspiration_only"
    assert summary["family_counts"] == {"null": 100}
    assert manifest["source_correspondence_claim"] is False
    assert all(
        "certified_base" not in path for path in manifest["outputs"]
    )
    assert_no_outputs(tmp_path)


def test_inspiration_only_underflow_writes_nothing(tmp_path):
    build_fixture(tmp_path)
    redteam_path = tmp_path / ASSEMBLER.REDTEAM_REVIEW
    redteam = read_jsonl(redteam_path)
    for row in redteam[:49]:
        row["verdict"] = "reject"
        row["reason_codes"] = ["blind_reject"]
    write_jsonl(redteam_path, redteam)
    assert (
        ASSEMBLER.main(
            ["--root", str(tmp_path), "--inspiration-only"]
        )
        == 1
    )
    assert_no_inspiration_outputs(tmp_path)
    assert_no_outputs(tmp_path)


def test_missing_or_duplicate_review_fails_closed(tmp_path):
    assert ASSEMBLER.main(["--root", str(tmp_path)]) == 1
    assert_no_outputs(tmp_path)

    build_fixture(tmp_path)
    redteam_path = tmp_path / ASSEMBLER.REDTEAM_REVIEW
    redteam = read_jsonl(redteam_path)
    write_jsonl(redteam_path, redteam + [redteam[0]])
    assert ASSEMBLER.main(["--root", str(tmp_path)]) == 1
    assert_no_outputs(tmp_path)


def test_pure_assembler_does_not_write(tmp_path):
    build_fixture(tmp_path)
    result = ASSEMBLER.assemble(tmp_path)
    assert result["summary"]["selected_count"] == 100
    assert_no_outputs(tmp_path)


def test_family_assignment_refuses_zero_evidence_families():
    eligible = []
    for index in range(100):
        eligible.append(
            {
                "candidate_id": f"C{index:03d}",
                "source_group": "supplemental_reserve2",
                "reserve_rank": index + 1,
                "original_problem_text": "A vehicle routing delivery problem.",
                "semantic_mapping": {
                    "variables": [{"name": "route"}],
                    "constraints": [{"name": "route_limit"}],
                    "objective": {"name": "route_cost"},
                },
                "_ir": {
                    "variables": [{"name": "route", "vartype": "I"}],
                    "constraints": [
                        {"name": "route_limit", "sense": "<=", "terms": {}}
                    ],
                    "objective": {"name": "route_cost"},
                },
            }
        )
    try:
        ASSEMBLER.balanced_family_selection(eligible, [])
    except ASSEMBLER.PoolAssemblyError as error:
        assert "fewer than ten evidence-backed candidates" in str(error)
        assert "healthcare_resources" in error.details["impossible_families"]
    else:
        raise AssertionError("zero-evidence family assignment was accepted")
